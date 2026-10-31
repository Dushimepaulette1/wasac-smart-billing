"""Staff correct a meter's current reading (app/services/meter_correction.py)."""
from datetime import datetime, timedelta

import pytest

from app.anomaly.features import ReadingPoint
from app.anomaly.service import since_last_reset
from app.models import Customer, Meter, StaffAction
from app.services.meter_correction import CorrectionError
from app.services.meter_correction_requests import approve_correction, decline_correction
from support.factories import add_household, add_officer, make_history
from support.clients import signed_in_client

METER = "MTR-C"
AT_THE_METER = {"lat": -1.9441, "lng": 30.0619, "accuracy_m": 15}


@pytest.fixture
def household(db):
    """A demo-like meter whose record (about 1000 m3) is far above the real meter (355 m3)."""
    start = datetime.utcnow() - timedelta(days=30 * 7)
    points = make_history([0.4] * 6, start=start, start_m3=1000.0)
    customer_id = add_household(db, METER, points)
    meter = db.get(Meter, METER)
    meter.gps_lat, meter.gps_lng = AT_THE_METER["lat"], AT_THE_METER["lng"]
    db.commit()
    return customer_id


@pytest.fixture
def supervisor(db):
    add_officer(db, username="sup1", role="supervisor")
    fastapi_app, c = signed_in_client(db, "sup1")
    yield c
    fastapi_app.dependency_overrides.clear()


def correct(c, customer_id, value, reason="Meter replaced in October"):
    return c.post(f"/customers/{customer_id}/meter-correction", json={"reading_m3": value, "reason": reason})


def corrected(db, c, customer_id, value):
    """Asked for by one supervisor, approved by another."""
    row = correct(c, customer_id, value).json()
    return approve_correction(db, row["id"], "sup2")


def test_when_a_supervisor_asks_should_change_nothing_until_a_second_person_approves(db, supervisor, household):
    before = db.get(Meter, METER).last_reading
    r = correct(supervisor, household, 355.036)
    assert r.status_code == 200 and r.json()["status"] == "awaiting_approval"
    assert db.get(Meter, METER).last_reading == before
    assert db.query(StaffAction).filter(StaffAction.action == "meter_correction_requested").count() == 1
    assert supervisor.get("/meter-corrections?status=awaiting_approval").json()[0]["reading_m3"] == 355.036


def test_when_the_person_who_asked_approves_should_refuse_it(db, supervisor, household):
    row = correct(supervisor, household, 355.036).json()
    r = supervisor.post(f"/meter-corrections/{row['id']}/approve")
    assert r.status_code == 403
    assert supervisor.get("/meter-corrections?status=awaiting_approval").json()[0]["id"] == row["id"]


def test_when_a_second_correction_is_asked_for_the_same_meter_should_refuse_it(supervisor, household):
    correct(supervisor, household, 355.036)
    r = correct(supervisor, household, 400.0)
    assert r.status_code == 409 and "already waiting" in r.json()["detail"]


def test_when_declined_should_leave_the_meter_and_record_why(db, supervisor, household):
    before = db.get(Meter, METER).last_reading
    row = correct(supervisor, household, 355.036).json()
    done = decline_correction(db, row["id"], "sup2", "The photo shows 1010")
    assert done.status == "declined" and done.decision_reason == "The photo shows 1010"
    assert db.get(Meter, METER).last_reading == before
    with pytest.raises(CorrectionError):
        approve_correction(db, row["id"], "sup3")


def test_when_the_record_changes_while_waiting_should_go_stale(db, supervisor, household):
    row = correct(supervisor, household, 355.036).json()
    db.get(Meter, METER).last_reading = 1100.0
    db.commit()
    with pytest.raises(CorrectionError) as refused:
        approve_correction(db, row["id"], "sup2")
    assert refused.value.status_code == 409
    assert supervisor.get("/meter-corrections?status=stale").json()[0]["id"] == row["id"]
    assert db.get(Meter, METER).last_reading == 1100.0


def test_when_a_meter_has_no_starting_value_should_apply_at_once(db, supervisor):
    db.add(Meter(meter_id="MTR-NEW", last_reading=0))
    db.flush()
    db.add(Customer(customer_id="CUST-NEW", name="New", phone="+250788000222", meter_id="MTR-NEW", sector="Test"))
    db.commit()
    r = correct(supervisor, "CUST-NEW", 120.5)
    assert r.status_code == 200 and r.json()["status"] == "applied"
    assert db.get(Meter, "MTR-NEW").last_reading == 120.5


def test_when_a_second_supervisor_approves_should_set_the_reading_and_log_it(db, supervisor, household):
    assert corrected(db, supervisor, household, 355.036).status == "applied"
    assert db.get(Meter, METER).last_reading == 355.036
    action = db.query(StaffAction).filter(StaffAction.action == "meter_corrected").one()
    assert action.target == METER and "-> 355.036 m3: Meter replaced in October" in action.detail


def test_when_an_officer_tries_to_correct_a_meter_should_refuse_it(client, household):
    assert correct(client, household, 355.036).status_code == 403


def test_when_the_meter_is_corrected_should_accept_the_next_reading_straight_away(db, supervisor, household_client, household):
    """The officer types what the meter shows; the household's photo soon after reads almost the same.
    Before the correction this reading was "lower than the last" (the record said about 1000 m3)."""
    corrected(db, supervisor, household, 355.036)
    body = household_client.post("/confirm-reading", json={
        "customer_id": household, "meter_id": METER, "confirmed_reading": "355.050", "location": AT_THE_METER,
    }).json()
    assert body["validation_status"] == "valid", body["anomaly"]
    assert body["bill_id"] and body["consumption_m3"] == pytest.approx(0.014, abs=0.001)


def test_when_the_meter_is_corrected_should_compare_later_readings_with_the_correction(db, supervisor, household):
    from app.anomaly.service import load_history

    corrected(db, supervisor, household, 355.036)
    history = load_history(db, METER, before=datetime.utcnow() + timedelta(days=1))
    assert [p.reading_m3 for p in history] == [355.036]  # the old 1000 m3 record is set aside


def test_when_a_reading_is_waiting_for_review_should_refuse_a_correction(supervisor, household_client, household):
    household_client.post("/confirm-reading", json={
        "customer_id": household, "meter_id": METER, "confirmed_reading": "300.000", "location": AT_THE_METER,
    })  # lower than the record: held
    r = correct(supervisor, household, 355.036)
    assert r.status_code == 409 and "review queue" in r.json()["detail"]


@pytest.mark.parametrize("value, reason", [(-1, "x replaced"), (100_000, "too big"), (355, "")])
def test_when_the_correction_is_invalid_should_refuse_it(supervisor, household, value, reason):
    assert correct(supervisor, household, value, reason).status_code == 422


def test_when_history_drops_should_start_from_the_drop():
    t = datetime(2026, 1, 1)
    points = [ReadingPoint(t + timedelta(days=30 * i), v) for i, v in enumerate([990, 1000, 1010, 355, 367])]
    assert [p.reading_m3 for p in since_last_reset(points)] == [355, 367]
    assert since_last_reset(points[:3]) == points[:3]
