"""Suspicious readings are held for WASAC staff instead of being billed or moving the meter."""
from datetime import datetime, timedelta

import pytest
from conftest import add_household, make_history

from database import Bill, Meter, Reading

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
    from anomaly.db_models import AnomalyFlag

    return db.get(Reading, db.get(AnomalyFlag, flag_id).reading_id)


def test_ten_x_misread_does_not_block_next_correct_reading(client, db, household, trained_model_on_disk):
    customer_id, last = household
    misread = confirm(client, customer_id, last + 0.4 * 30 * 10)
    assert misread["anomaly"]["model_used"]
    assert misread["anomaly"]["anomaly_type"] == "MISREAD_SUSPECTED"
    assert misread["validation_status"] == "pending_review" and misread["bill_id"] is None
    assert db.get(Meter, METER).last_reading == last

    correct = confirm(client, customer_id, last + 0.4 * 30)
    assert correct["success"] and correct["validation_status"] == "valid"
    assert correct["consumption_m3"] == pytest.approx(12.0, abs=0.01)  # measured from the last CONFIRMED reading
    assert correct["bill_id"] is not None
    assert db.get(Meter, METER).last_reading == pytest.approx(last + 12)


def test_reading_below_last_confirmed_is_held_not_rejected(client, db, household):
    customer_id, last = household
    body = confirm(client, customer_id, last - 7)
    assert body["success"] is True
    assert body["validation_status"] == "pending_review"
    assert body["anomaly"]["anomaly_type"] == "MISREAD_SUSPECTED"
    assert "being checked" in body["anomaly"]["message_for_household"]
    assert body["bill_id"] is None
    assert db.get(Meter, METER).last_reading == last


def test_accept_confirms_and_bills_the_reading(client, db, household):
    customer_id, last = household
    held = confirm(client, customer_id, last + 200)  # ~6.7 m3/day: SPIKE rule
    flag_id = held["anomaly"]["flag_id"]

    r = client.patch(f"/api/anomaly/flags/{flag_id}/resolve", json={"outcome": "accept"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "resolved" and body["outcome"] == "accept"
    assert body["reading_status"] == "valid" and body["bill_id"] and body["amount_due"] > 0
    assert "sms_household_logged" in body["actions"]

    reading = reading_for(db, flag_id)
    assert reading.validation_status == "valid"
    assert [b.consumption_m3 for b in bills_for(db, reading.reading_id)] == [pytest.approx(200)]
    assert db.get(Meter, METER).last_reading == pytest.approx(last + 200)


def test_reject_discards_the_reading_and_asks_to_resubmit(client, db, household):
    customer_id, last = household
    held = confirm(client, customer_id, last + 200)
    flag_id = held["anomaly"]["flag_id"]

    body = client.patch(f"/api/anomaly/flags/{flag_id}/resolve", json={"outcome": "reject"}).json()
    assert body["status"] == "resolved" and body["outcome"] == "reject"
    assert body["reading_status"] == "rejected" and body["bill_id"] is None
    assert "sms_household_logged" in body["actions"]

    reading = reading_for(db, flag_id)
    assert reading.validation_status == "rejected"
    assert bills_for(db, reading.reading_id) == []
    assert db.get(Meter, METER).last_reading == last

    # The household's resubmission is judged against the last confirmed reading, not the rejected one.
    again = confirm(client, customer_id, last + 12)
    assert again["validation_status"] == "valid" and again["consumption_m3"] == pytest.approx(12, abs=0.01)


def test_pending_flag_needs_an_outcome(client, household):
    customer_id, last = household
    flag_id = confirm(client, customer_id, last + 200)["anomaly"]["flag_id"]
    assert client.patch(f"/api/anomaly/flags/{flag_id}/resolve").status_code == 422
    assert client.patch(f"/api/anomaly/flags/{flag_id}/resolve", json={"outcome": "maybe"}).status_code == 422


def test_outcome_on_a_flag_without_pending_reading_is_refused(client, household):
    r = client.post("/api/anomaly/score", json={"household_id": METER, "reading_digits": "123"})
    flag_id = r.json()["flag_id"]
    assert r.json()["needs_retake"]
    assert client.patch(f"/api/anomaly/flags/{flag_id}/resolve", json={"outcome": "accept"}).status_code == 409
    assert client.patch(f"/api/anomaly/flags/{flag_id}/resolve").json()["status"] == "resolved"


def test_cannot_accept_once_a_newer_reading_is_confirmed(client, db, household):
    customer_id, last = household
    flag_id = confirm(client, customer_id, last + 200)["anomaly"]["flag_id"]
    assert confirm(client, customer_id, last + 12)["validation_status"] == "valid"

    r = client.patch(f"/api/anomaly/flags/{flag_id}/resolve", json={"outcome": "accept"})
    assert r.status_code == 409
    assert reading_for(db, flag_id).validation_status == "pending_review"
    assert db.get(Meter, METER).last_reading == pytest.approx(last + 12)


def test_pending_reading_is_not_used_as_history_for_next_score(client, db, household):
    customer_id, last = household
    confirm(client, customer_id, last + 200)  # held
    nxt = confirm(client, customer_id, last + 12)
    assert nxt["anomaly"]["features"]["previous_reading_m3"] == pytest.approx(last)
    assert nxt["anomaly"]["features"]["n_history"] == len(DAILIES)


def test_imported_meter_without_history_still_holds_lower_reading(client, db):
    from database import Customer

    db.add(Meter(meter_id=METER, last_reading=800.0))
    db.add(Customer(customer_id="CUST900", name="Imported", phone="+250788000222", meter_id=METER, sector="X"))
    db.commit()
    body = confirm(client, "CUST900", 750.0)
    assert body["validation_status"] == "pending_review"
    assert body["anomaly"]["anomaly_type"] == "MISREAD_SUSPECTED" and body["anomaly"]["flag_id"]
    assert db.get(Meter, METER).last_reading == 800.0
