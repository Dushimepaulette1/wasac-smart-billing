"""A meter with no starting value (added without a first reading): its first reading is held, and
accepting it records the starting point without a bill. Billing it would charge the whole register."""
from datetime import datetime, timedelta

import pytest

from app.models import AnomalyFlag, Bill, Customer, Meter, Reading
from app.services.reading_window import reading_block
from support.factories import add_household, make_history

METER = "MTR-NEW"
CUSTOMER = "CUST-NEW"


@pytest.fixture
def new_household(db):
    """As staff add a household without a first reading: last_reading 0 and no readings."""
    db.add(Meter(meter_id=METER, last_reading=0.0))
    db.add(Customer(customer_id=CUSTOMER, name="New", phone="+250788000111", meter_id=METER, sector="Test"))
    db.flush()
    db.get(Meter, METER).customer_id = CUSTOMER
    db.commit()


def confirm(c, value, **extra):
    return c.post("/confirm-reading", json={
        "customer_id": CUSTOMER, "meter_id": METER, "confirmed_reading": f"{value:.3f}", **extra,
    })


def test_when_a_meter_has_no_starting_value_should_hold_its_first_reading_unbilled(db, household_client, new_household):
    body = confirm(household_client, 431.46).json()
    assert body["validation_status"] == "pending_review" and body["bill_id"] is None
    assert body["anomaly"]["anomaly_type"] == "NO_BASELINE" and body["anomaly"]["pending_review"]
    assert db.query(Bill).count() == 0
    assert db.get(Meter, METER).last_reading == 0.0
    flag = db.get(AnomalyFlag, body["anomaly"]["flag_id"])
    assert flag.requires_staff_review and flag.status == "open"


def test_when_an_officer_accepts_a_first_reading_should_record_the_starting_point_without_a_bill(
    db, client, household_client, new_household,
):
    flag_id = confirm(household_client, 431.46).json()["anomaly"]["flag_id"]
    r = client.patch(f"/api/anomaly/flags/{flag_id}/resolve", json={"outcome": "accept"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["reading_status"] == "valid" and body["bill_id"] is None and body["amount_due"] is None
    assert "sms_household_not_sent" in body["actions"]  # the starting-point SMS was tried (SMS off in tests)
    assert db.query(Bill).count() == 0
    reading = db.get(Reading, db.get(AnomalyFlag, flag_id).reading_id)
    assert reading.validation_status == "valid" and reading.implied_consumption is None
    assert db.get(Meter, METER).last_reading == pytest.approx(431.46)


def test_when_the_starting_point_is_accepted_should_bill_the_next_reading_from_it(
    db, client, household_client, new_household,
):
    flag_id = confirm(household_client, 431.46).json()["anomaly"]["flag_id"]
    client.patch(f"/api/anomaly/flags/{flag_id}/resolve", json={"outcome": "accept"})
    # Staff enter it: a household's photo without a location would be held by the location check.
    # Within a day of the starting point: 4 m3 stays under the 5 m3/day spike rule.
    body = confirm(client, 435.46).json()
    assert body["validation_status"] == "valid" and body["bill_id"]
    assert body["consumption_m3"] == pytest.approx(4.0)


def test_when_the_starting_point_is_accepted_should_start_the_25_day_interval(
    db, client, household_client, new_household,
):
    flag_id = confirm(household_client, 431.46).json()["anomaly"]["flag_id"]
    client.patch(f"/api/anomaly/flags/{flag_id}/resolve", json={"outcome": "accept"})
    block = reading_block(db, db.get(Meter, METER))
    assert block is not None and block.reason == "too_soon"
    assert confirm(household_client, 443.46).status_code == 409


def test_when_a_first_reading_is_rejected_should_allow_a_new_first_reading(db, client, household_client, new_household):
    flag_id = confirm(household_client, 4314.6).json()["anomaly"]["flag_id"]
    client.patch(f"/api/anomaly/flags/{flag_id}/resolve", json={"outcome": "reject", "reason": "Digits misread"})
    again = confirm(household_client, 431.46).json()
    assert again["anomaly"]["anomaly_type"] == "NO_BASELINE" and again["bill_id"] is None


def test_when_staff_added_the_household_with_a_first_reading_should_bill_as_before(db, client):
    r = client.post("/customers", json={
        "name": "Uwase", "phone": "0788000111", "meter_id": "KGL-31001", "sector": "Kicukiro", "first_reading": "420.5",
    })
    assert r.status_code == 201, r.text
    body = client.post("/confirm-reading", json={
        "customer_id": r.json()["customer_id"], "meter_id": "KGL-31001", "confirmed_reading": "424.500",
    }).json()
    assert body["validation_status"] == "valid" and body["consumption_m3"] == pytest.approx(4.0)


def test_when_an_imported_meter_has_a_stored_reading_but_no_rows_should_bill_as_before(db, client):
    db.add(Meter(meter_id=METER, last_reading=420.5, last_reading_date=datetime.utcnow() - timedelta(days=30)))
    db.add(Customer(customer_id=CUSTOMER, name="Old", phone="+250788000111", meter_id=METER, sector="Test"))
    db.commit()
    body = confirm(client, 432.5).json()
    assert body["validation_status"] == "valid" and body["consumption_m3"] == pytest.approx(12.0)


def test_when_a_ussd_first_reading_is_sent_should_hold_it(db, anon_client, new_household, monkeypatch):
    monkeypatch.setenv("USSD_CALLBACK_TOKEN", "t0ken")
    r = anon_client.post("/ussd?token=t0ken", data={"sessionId": "s1", "serviceCode": "*1#",
                                                     "phoneNumber": "+250788000111", "text": "1*00431460*1"})
    assert r.status_code == 200, r.text
    assert db.query(Bill).count() == 0
    assert db.query(Reading).one().validation_status == "pending_review"


def test_when_history_exists_should_not_call_it_a_first_reading(db, client):
    points = make_history([0.4] * 4, start=datetime.utcnow() - timedelta(days=150))
    customer_id = add_household(db, "MTR-OLD", points)
    body = client.post("/confirm-reading", json={
        "customer_id": customer_id, "meter_id": "MTR-OLD", "confirmed_reading": f"{points[-1].reading_m3 + 12:.3f}",
    }).json()
    assert body["anomaly"]["anomaly_type"] != "NO_BASELINE" and body["bill_id"]
