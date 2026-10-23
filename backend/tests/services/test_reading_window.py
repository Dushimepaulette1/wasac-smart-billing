"""One reading per billing period, one at a time (app/services/reading_window.py)."""
from datetime import datetime, timedelta

import pytest

from app.models import Meter
from support.factories import add_household, make_history

METER = "MTR-W"
AT_THE_METER = {"lat": -1.9441, "lng": 30.0619, "accuracy_m": 15}


@pytest.fixture
def household(db):
    """Last accepted reading 30 days ago, so a new reading is open; the meter's location is on file."""
    start = datetime.utcnow() - timedelta(days=30 * 7)
    points = make_history([0.4] * 6, start=start)
    customer_id = add_household(db, METER, points)
    meter = db.get(Meter, METER)
    meter.gps_lat, meter.gps_lng = AT_THE_METER["lat"], AT_THE_METER["lng"]
    db.commit()
    return customer_id, points[-1].reading_m3


def confirm(c, customer_id, value):
    return c.post("/confirm-reading", json={
        "customer_id": customer_id, "meter_id": METER, "confirmed_reading": f"{value:.3f}", "location": AT_THE_METER,
    })


def test_when_a_reading_is_waiting_for_an_officer_should_refuse_another(household_client, client, household):
    customer_id, last = household
    assert confirm(household_client, customer_id, last + 300).json()["validation_status"] == "pending_review"  # a spike
    again = confirm(household_client, customer_id, last + 12)
    assert again.status_code == 409 and "still being checked" in again.json()["detail"]
    info = household_client.get(f"/customers/{customer_id}").json()
    assert info["reading_pending"] is True and info["next_reading_from"] is None
    # Staff can still enter a reading (a field officer at the meter).
    assert confirm(client, customer_id, last + 12).status_code == 200


def test_when_this_periods_reading_is_in_should_refuse_until_the_next_opens(household_client, household):
    customer_id, last = household
    assert confirm(household_client, customer_id, last + 12).json()["validation_status"] == "valid"
    again = confirm(household_client, customer_id, last + 13)
    assert again.status_code == 409 and "next one opens on" in again.json()["detail"]
    info = household_client.get(f"/customers/{customer_id}").json()
    assert info["reading_pending"] is False
    opens = datetime.fromisoformat(info["next_reading_from"])
    assert timedelta(days=24) < opens - datetime.utcnow() <= timedelta(days=25)


def test_when_min_days_is_0_should_allow_readings_any_time(household_client, household, monkeypatch):
    monkeypatch.setenv("MIN_DAYS_BETWEEN_READINGS", "0")
    customer_id, last = household
    assert confirm(household_client, customer_id, last + 12).status_code == 200
    assert confirm(household_client, customer_id, last + 13).status_code == 200


def test_when_a_rejected_reading_is_followed_by_a_new_one_should_allow_it(household_client, client, household):
    customer_id, last = household
    flag_id = confirm(household_client, customer_id, last + 300).json()["anomaly"]["flag_id"]
    client.patch(f"/api/anomaly/flags/{flag_id}/resolve", json={"outcome": "reject"})
    assert confirm(household_client, customer_id, last + 12).status_code == 200


def test_when_a_ussd_reading_is_sent_while_one_is_waiting_should_refuse_it(anon_client, household_client, household, monkeypatch):
    monkeypatch.setenv("USSD_CALLBACK_TOKEN", "t")
    customer_id, last = household
    confirm(household_client, customer_id, last + 300)
    r = anon_client.post("/ussd?token=t", data={"phoneNumber": "+250788000111", "text": "9*1"})
    assert "still being checked" in r.text
