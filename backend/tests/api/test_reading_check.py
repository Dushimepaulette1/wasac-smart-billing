"""POST /check-reading: what sending a reading would lead to, with nothing stored. /confirm-reading
runs the same checks (evaluate_reading) again when the reading is sent, so the two always agree."""
from datetime import datetime, timedelta

import pytest

from app.models import AnomalyFlag, Bill, Customer, Meter, PhotoRead, Reading, ReadingEvidence
from app.services.meter_correction import correct_meter
from support.factories import add_household, make_history

METER = "MTR-CK"
LAT, LNG = -1.9441, 30.0619
NEAR = {"lat": LAT, "lng": LNG, "accuracy_m": 15}
FAR = {"lat": LAT - 0.02, "lng": LNG, "accuracy_m": 15}  # about 2 km away


@pytest.fixture
def household(db):
    points = make_history([0.4] * 6, start=datetime.utcnow() - timedelta(days=210))
    customer_id = add_household(db, METER, points)
    meter = db.get(Meter, METER)
    meter.gps_lat, meter.gps_lng = LAT, LNG
    db.commit()
    return customer_id, points[-1].reading_m3


def body(customer_id, value, location=NEAR, photo_id=None, meter=METER):
    return {"customer_id": customer_id, "meter_id": meter, "confirmed_reading": f"{value:.3f}",
            "location": location, "photo_id": photo_id}


def counts(db):
    return (db.query(Reading).count(), db.query(Bill).count(), db.query(AnomalyFlag).count(),
            db.query(ReadingEvidence).count(), db.get(Meter, METER).last_reading)


def add_photo(db, digits, pid="ph1", owner="household:+250788000111"):
    db.add(PhotoRead(id=pid, owner=owner, reader_digits=digits, confidence_min=0.9, guidance="OK"))
    db.commit()
    return pid


# (change from the last reading, location, AI digits or None, expected reason or None)
CASES = {
    "normal": (12.0, NEAR, None, None),
    "lower than the last reading": (-0.06, NEAR, None, "below_previous"),
    "much higher than usual": (60.0, NEAR, None, "high_use"),
    "about 10x the usual": (120.0, NEAR, None, "misread"),
    "photo taken far away": (12.0, FAR, None, "location"),
    "lowered the AI read by 2 m3": (12.0, NEAR, "+14", "edited_down"),
}


def _ai_digits(last, spec):
    return None if spec is None else f"{round((last + float(spec)) * 1000):08d}"


@pytest.mark.parametrize("delta, where, ai, reason", CASES.values(), ids=CASES.keys())
def test_when_a_reading_is_checked_should_give_the_reason_and_store_nothing(
    db, household_client, household, delta, where, ai, reason,
):
    customer_id, last = household
    pid = add_photo(db, _ai_digits(last, ai)) if ai else None
    before = counts(db)
    r = household_client.post("/check-reading", json=body(customer_id, last + delta, where, pid))
    assert r.status_code == 200, r.text
    answer = r.json()
    assert answer["needs_review"] == (reason is not None) and answer["reason"] == reason
    assert answer["previous_reading_m3"] == pytest.approx(last) and answer["refused"] is None
    assert answer["consumption_m3"] == pytest.approx(delta, abs=0.001)
    assert counts(db) == before
    if pid:
        assert db.get(PhotoRead, pid).reading_id is None  # the photo is not used up by a check


@pytest.mark.parametrize("delta, where, ai, reason", CASES.values(), ids=CASES.keys())
def test_when_the_checked_reading_is_sent_should_get_the_same_answer(
    db, household_client, household, delta, where, ai, reason,
):
    customer_id, last = household
    pid = add_photo(db, _ai_digits(last, ai)) if ai else None
    checked = household_client.post("/check-reading", json=body(customer_id, last + delta, where, pid)).json()
    sent = household_client.post("/confirm-reading", json=body(customer_id, last + delta, where, pid)).json()
    assert (sent["validation_status"] == "pending_review") == checked["needs_review"]
    assert (sent["bill_id"] is None) == checked["needs_review"]


def test_when_the_meter_has_no_starting_value_should_say_first_reading(db, household_client):
    db.add(Meter(meter_id="MTR-NB", last_reading=0.0, gps_lat=LAT, gps_lng=LNG))
    db.flush()
    db.add(Customer(customer_id="CUST-NB", name="New", phone="+250788000111", meter_id="MTR-NB"))
    db.commit()
    answer = household_client.post("/check-reading", json=body("CUST-NB", 431.46, meter="MTR-NB")).json()
    assert answer["needs_review"] and answer["reason"] == "first_reading"


def test_when_a_reading_is_waiting_for_an_officer_should_say_it_cannot_be_sent(db, household_client, household):
    customer_id, last = household
    household_client.post("/confirm-reading", json=body(customer_id, last - 1))  # held
    answer = household_client.post("/check-reading", json=body(customer_id, last + 12)).json()
    assert answer["refused"] == "pending" and not answer["needs_review"]


def test_when_this_periods_reading_is_in_should_say_when_the_next_opens(db, household_client, household):
    customer_id, last = household
    assert household_client.post("/confirm-reading", json=body(customer_id, last + 12)).json()["bill_id"]
    answer = household_client.post("/check-reading", json=body(customer_id, last + 13)).json()
    assert answer["refused"] == "too_soon" and answer["opens_on"]


def test_when_staff_check_a_value_just_sent_should_say_duplicate(db, client, household):
    customer_id, last = household
    client.post("/confirm-reading", json=body(customer_id, last + 12))
    assert client.post("/check-reading", json=body(customer_id, last + 12)).json()["refused"] == "duplicate"


def test_when_checking_another_households_meter_should_not_find_it(db, household_client, anon_client, household):
    other = add_household(db, "MTR-OTHER", make_history([0.4] * 3), phone="+250788222333")
    r = household_client.post("/check-reading", json=body(other, 600.0, meter="MTR-OTHER"))
    assert r.status_code == 404
    assert anon_client.post("/check-reading", json=body(household[0], 600.0)).status_code == 401


def test_when_the_reading_is_not_plain_digits_should_refuse_it(household_client, household):
    r = household_client.post("/check-reading", json={**body(household[0], 1.0), "confirmed_reading": "1e3"})
    assert r.status_code == 422


def test_when_the_baseline_changes_after_the_check_should_hold_the_reading_on_sending(db, household_client, household):
    customer_id, last = household
    assert not household_client.post("/check-reading", json=body(customer_id, last + 12)).json()["needs_review"]
    correct_meter(db, db.get(Meter, METER), last + 20)  # e.g. a supervisor corrects the meter meanwhile
    db.commit()
    sent = household_client.post("/confirm-reading", json=body(customer_id, last + 12)).json()
    assert sent["validation_status"] == "pending_review" and sent["bill_id"] is None


def test_when_a_reading_arrives_from_elsewhere_after_the_check_should_refuse_on_sending(db, household_client, household):
    customer_id, last = household
    assert household_client.post("/check-reading", json=body(customer_id, last + 12)).json()["refused"] is None
    db.add(Reading(meter_id=METER, submitted_value=last + 5, submission_time=datetime.utcnow(),
                   validation_status="pending_review"))  # e.g. sent by USSD meanwhile
    db.commit()
    assert household_client.post("/confirm-reading", json=body(customer_id, last + 12)).status_code == 409


def test_when_too_many_checks_are_sent_should_slow_the_caller_down(household_client, household):
    customer_id, last = household
    codes = [household_client.post("/check-reading", json=body(customer_id, last + 12)).status_code for _ in range(21)]
    assert codes[:20] == [200] * 20 and codes[20] == 429


def test_when_the_same_photo_is_sent_again_should_return_the_first_result_and_store_nothing(
    db, household_client, household,
):
    customer_id, last = household
    pid = add_photo(db, _ai_digits(last, "12"))
    first = household_client.post("/confirm-reading", json=body(customer_id, last + 12, photo_id=pid)).json()
    before = counts(db)
    again = household_client.post("/confirm-reading", json=body(customer_id, last + 12, photo_id=pid))
    assert again.status_code == 200
    assert again.json()["repeated"] and again.json()["bill_id"] == first["bill_id"]
    assert again.json()["validation_status"] == first["validation_status"]
    assert counts(db) == before


def test_when_a_held_reading_is_sent_again_should_say_it_is_still_held(db, household_client, household):
    customer_id, last = household
    pid = add_photo(db, _ai_digits(last, "-1"))
    household_client.post("/confirm-reading", json=body(customer_id, last - 1, photo_id=pid))
    again = household_client.post("/confirm-reading", json=body(customer_id, last - 1, photo_id=pid)).json()
    assert again["repeated"] and again["validation_status"] == "pending_review"
    assert again["anomaly"]["pending_review"] and again["anomaly"]["anomaly_type"] == "MISREAD_SUSPECTED"


def test_when_the_photo_was_used_for_a_rejected_reading_should_ask_for_a_new_photo(db, household_client, client, household):
    customer_id, last = household
    pid = add_photo(db, _ai_digits(last, "-1"))
    flag_id = household_client.post("/confirm-reading", json=body(customer_id, last - 1, photo_id=pid)).json()["anomaly"]["flag_id"]
    client.patch(f"/api/anomaly/flags/{flag_id}/resolve", json={"outcome": "reject", "reason": "Unclear photo"})
    r = household_client.post("/confirm-reading", json=body(customer_id, last - 1, photo_id=pid))
    assert r.status_code == 409 and "new photo" in r.json()["detail"]
