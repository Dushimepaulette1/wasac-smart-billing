"""Suspicious readings are held for WASAC staff instead of being billed or moving the meter."""
from datetime import datetime, timedelta
import pytest
from app.models import Bill, Meter, Reading
from support.factories import add_household, make_history


METER = "MTR900"


DAILIES = [0.38, 0.42, 0.40, 0.41, 0.39, 0.43, 0.40, 0.37]


@pytest.fixture
def household(db):
    """History whose last confirmed reading is 30 days ago, so 'now' submissions are ~30-day periods."""
    start = datetime.utcnow() - timedelta(days=30 * (len(DAILIES) + 1))
    points = make_history(DAILIES, start=start)
    customer_id = add_household(db, METER, points)
    return customer_id, points[-1].reading_m3


def confirm(client, customer_id, value):
    return client.post("/confirm-reading", json={
        "customer_id": customer_id, "meter_id": METER, "confirmed_reading": str(round(value, 3)),
    }).json()


def bills_for(db, reading_id):
    return db.query(Bill).filter(Bill.reading_id == reading_id).all()


def reading_for(db, flag_id):
    from app.models import AnomalyFlag

    return db.get(Reading, db.get(AnomalyFlag, flag_id).reading_id)


def test_when_a_10x_misread_is_held_should_not_block_the_next_correct_reading(client, db, household, trained_model_on_disk):
    customer_id, last = household
    misread = confirm(client, customer_id, last + 0.4 * 30 * 10)
    # The rule-based history check catches a 10x jump before the model is asked (it used to be the
    # model alone); the outcome is the same: held as a suspected misread.
    assert not misread["anomaly"]["model_used"] and misread["anomaly"]["features"]["digit_shift"]
    assert misread["anomaly"]["anomaly_type"] == "MISREAD_SUSPECTED"
    assert misread["validation_status"] == "pending_review" and misread["bill_id"] is None
    assert db.get(Meter, METER).last_reading == last

    correct = confirm(client, customer_id, last + 0.4 * 30)
    assert correct["success"] and correct["validation_status"] == "valid"
    assert correct["consumption_m3"] == pytest.approx(12.0, abs=0.01)  # measured from the last CONFIRMED reading
    assert correct["bill_id"] is not None
    assert db.get(Meter, METER).last_reading == pytest.approx(last + 12)


def test_when_a_reading_is_below_the_last_confirmed_should_hold_it_not_reject_it(client, db, household):
    customer_id, last = household
    body = confirm(client, customer_id, last - 7)
    assert body["success"] is True
    assert body["validation_status"] == "pending_review"
    assert body["anomaly"]["anomaly_type"] == "MISREAD_SUSPECTED"
    assert "being checked" in body["anomaly"]["message_for_household"]
    assert body["bill_id"] is None
    assert db.get(Meter, METER).last_reading == last


def test_when_an_officer_accepts_should_confirm_and_bill_the_reading(client, db, household):
    customer_id, last = household
    held = confirm(client, customer_id, last + 200)  # ~6.7 m3/day: SPIKE rule
    flag_id = held["anomaly"]["flag_id"]

    r = client.patch(f"/api/anomaly/flags/{flag_id}/resolve", json={"outcome": "accept"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "resolved" and body["outcome"] == "accept"
    assert body["reading_status"] == "valid" and body["bill_id"] and body["amount_due"] > 0
    assert "sms_household_not_sent" in body["actions"]  # SMS is off in tests

    reading = reading_for(db, flag_id)
    assert reading.validation_status == "valid"
    assert [b.consumption_m3 for b in bills_for(db, reading.reading_id)] == [pytest.approx(200)]
    assert db.get(Meter, METER).last_reading == pytest.approx(last + 200)


def test_when_an_officer_rejects_should_discard_the_reading_and_ask_for_a_new_one(client, db, household):
    customer_id, last = household
    held = confirm(client, customer_id, last + 200)
    flag_id = held["anomaly"]["flag_id"]

    body = client.patch(f"/api/anomaly/flags/{flag_id}/resolve", json={"outcome": "reject", "reason": "Photo not clear"}).json()
    assert body["status"] == "resolved" and body["outcome"] == "reject"
    assert body["reading_status"] == "rejected" and body["bill_id"] is None
    assert "sms_household_not_sent" in body["actions"]  # SMS is off in tests

    reading = reading_for(db, flag_id)
    assert reading.validation_status == "rejected"
    assert bills_for(db, reading.reading_id) == []
    assert db.get(Meter, METER).last_reading == last

    # The household's resubmission is judged against the last confirmed reading, not the rejected one.
    again = confirm(client, customer_id, last + 12)
    assert again["validation_status"] == "valid" and again["consumption_m3"] == pytest.approx(12, abs=0.01)


def test_when_a_pending_flag_is_resolved_without_an_outcome_should_refuse_it(client, household):
    customer_id, last = household
    flag_id = confirm(client, customer_id, last + 200)["anomaly"]["flag_id"]
    assert client.patch(f"/api/anomaly/flags/{flag_id}/resolve").status_code == 422
    assert client.patch(f"/api/anomaly/flags/{flag_id}/resolve", json={"outcome": "maybe"}).status_code == 422


def test_when_an_outcome_is_given_for_a_flag_without_a_pending_reading_should_refuse_it(client, household):
    r = client.post("/api/anomaly/score", json={"household_id": METER, "reading_digits": "123"})
    flag_id = r.json()["flag_id"]
    assert r.json()["needs_retake"]
    assert client.patch(f"/api/anomaly/flags/{flag_id}/resolve", json={"outcome": "accept"}).status_code == 409
    assert client.patch(f"/api/anomaly/flags/{flag_id}/resolve").json()["status"] == "resolved"


def test_when_a_newer_reading_is_confirmed_should_refuse_to_accept_the_old_one(client, db, household):
    customer_id, last = household
    flag_id = confirm(client, customer_id, last + 200)["anomaly"]["flag_id"]
    assert confirm(client, customer_id, last + 12)["validation_status"] == "valid"

    r = client.patch(f"/api/anomaly/flags/{flag_id}/resolve", json={"outcome": "accept"})
    assert r.status_code == 409
    assert reading_for(db, flag_id).validation_status == "pending_review"
    assert db.get(Meter, METER).last_reading == pytest.approx(last + 12)


def test_when_a_reading_is_pending_should_not_use_it_as_history(client, db, household):
    customer_id, last = household
    confirm(client, customer_id, last + 200)  # held
    nxt = confirm(client, customer_id, last + 12)
    assert nxt["anomaly"]["features"]["previous_reading_m3"] == pytest.approx(last)
    assert nxt["anomaly"]["features"]["n_history"] == len(DAILIES)


def test_when_an_imported_meter_has_no_history_should_still_hold_a_lower_reading(client, db):
    from app.models import Customer

    db.add(Meter(meter_id=METER, last_reading=800.0))
    db.add(Customer(customer_id="CUST900", name="Imported", phone="+250788000222", meter_id=METER, sector="X"))
    db.commit()
    body = confirm(client, "CUST900", 750.0)
    assert body["validation_status"] == "pending_review"
    assert body["anomaly"]["anomaly_type"] == "MISREAD_SUSPECTED" and body["anomaly"]["flag_id"]
    assert db.get(Meter, METER).last_reading == 800.0


def test_when_a_household_lists_its_flags_should_include_the_reading_outcome(client, db, household):
    customer_id, last = household
    flag_id = confirm(client, customer_id, last + 200)["anomaly"]["flag_id"]
    flags = client.get("/api/anomaly/flags", params={"household_id": METER}).json()
    assert [f["reading_status"] for f in flags if f["id"] == flag_id] == ["pending_review"]

    client.patch(f"/api/anomaly/flags/{flag_id}/resolve", json={"outcome": "reject", "reason": "Photo not clear"})
    flags = client.get("/api/anomaly/flags", params={"household_id": METER}).json()
    assert [f["reading_status"] for f in flags if f["id"] == flag_id] == ["rejected"]


def test_when_the_same_reading_is_sent_twice_should_store_and_bill_it_once(client, db, household):
    customer_id, last = household
    first = confirm(client, customer_id, last + 12)  # a retry or a double tap
    again = client.post("/confirm-reading", json={
        "customer_id": customer_id, "meter_id": METER, "confirmed_reading": str(round(last + 12, 3)),
    })
    assert first["bill_id"] and again.status_code == 409 and "just sent" in again.json()["detail"]
    assert db.query(Reading).filter(Reading.meter_id == METER, Reading.submitted_value == round(last + 12, 3)).count() == 1
    assert db.query(Bill).count() == 1


def test_when_two_officers_decide_the_same_reading_should_bill_it_once(client, db, household):
    customer_id, last = household
    flag_id = confirm(client, customer_id, last + 200)["anomaly"]["flag_id"]
    assert client.patch(f"/api/anomaly/flags/{flag_id}/resolve", json={"outcome": "accept"}).status_code == 200
    second = client.patch(f"/api/anomaly/flags/{flag_id}/resolve", json={"outcome": "accept"})
    assert second.status_code == 409 and "already decided" in second.json()["detail"]
    assert len(bills_for(db, reading_for(db, flag_id).reading_id)) == 1


def test_when_a_second_bill_is_added_for_a_reading_should_be_refused_by_the_database(db):
    from sqlalchemy.exc import IntegrityError

    db.add(Reading(meter_id="MTR-U", submitted_value=1.0, validation_status="valid"))
    db.flush()
    reading_id = db.query(Reading.reading_id).filter(Reading.meter_id == "MTR-U").scalar()
    db.add_all([Bill(reading_id=reading_id, amount_due=1000), Bill(reading_id=reading_id, amount_due=1000)])
    with pytest.raises(IntegrityError):
        db.commit()


def test_when_an_older_database_lacks_the_bill_index_should_add_it():
    from sqlalchemy import create_engine, inspect, text
    from app.db.init_db import add_late_indexes

    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE bills (bill_id INTEGER PRIMARY KEY, reading_id INTEGER)"))
    add_late_indexes(engine)
    add_late_indexes(engine)  # every start-up: no error the second time
    assert any(i["name"] == "uq_bills_reading_id" and i["unique"] for i in inspect(engine).get_indexes("bills"))
