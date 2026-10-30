"""A register turning over past 99999.999: held, and billed across the wrap when an officer accepts it."""
from datetime import datetime, timedelta

import pytest

from app.anomaly.readings import rollover_consumption
from app.models import Bill, Meter
from support.factories import add_household, make_history

METER = "MTR-RO"


@pytest.fixture
def household(db):
    points = make_history([0.4] * 4, start=datetime.utcnow() - timedelta(days=150), start_m3=99_900.0)
    return add_household(db, METER, points), points[-1].reading_m3


def confirm(c, customer_id, value):
    return c.post("/confirm-reading", json={"customer_id": customer_id, "meter_id": METER, "confirmed_reading": f"{value:.3f}"})


def test_when_values_are_near_both_ends_should_count_across_the_wrap():
    assert rollover_consumption(99_950.0, 10.0) == pytest.approx(60.0)
    assert rollover_consumption(98_000.0, 10.0) is None  # lower, but not near the top
    assert rollover_consumption(99_950.0, 5_000.0) is None


def test_when_the_register_turns_over_should_hold_it_then_bill_the_use_across_the_wrap(db, client, household):
    customer_id, last = household
    body = confirm(client, customer_id, 7.0).json()
    assert body["anomaly"]["anomaly_type"] == "ROLLOVER" and body["validation_status"] == "pending_review"
    expected = 100_000 - last + 7
    assert body["consumption_m3"] == pytest.approx(expected)
    assert db.query(Bill).count() == 0
    done = client.patch(f"/api/anomaly/flags/{body['anomaly']['flag_id']}/resolve", json={"outcome": "accept"}).json()
    assert db.get(Bill, done["bill_id"]).consumption_m3 == pytest.approx(expected)
    assert db.get(Meter, METER).last_reading == 7.0


def test_when_checked_should_say_rollover(db, client, household):
    customer_id, _ = household
    answer = client.post("/check-reading", json={"customer_id": customer_id, "meter_id": METER, "confirmed_reading": "00007.000"}).json()
    assert answer["reason"] == "rollover"


def test_when_rejected_should_leave_the_meter_alone(db, client, household):
    customer_id, last = household
    flag = confirm(client, customer_id, 7.0).json()["anomaly"]["flag_id"]
    client.patch(f"/api/anomaly/flags/{flag}/resolve", json={"outcome": "reject", "reason": "Misread"})
    assert db.get(Meter, METER).last_reading == last
