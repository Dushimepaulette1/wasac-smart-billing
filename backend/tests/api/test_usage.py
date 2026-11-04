"""GET /customers/{id}/usage, and the leak SMS sent with a bill (app/services/usage.py)."""
from datetime import datetime, timedelta

import pytest

from app.models import Bill, Reading
from support.factories import add_household, make_history

METER = "MTR-US"


@pytest.fixture
def household(db):
    """0.4 m3 a day for six months; the newest reading was 30 days ago."""
    points = make_history([0.4] * 6, start=datetime.utcnow() - timedelta(days=210))
    return add_household(db, METER, points), points[-1].reading_m3


@pytest.fixture
def sent(monkeypatch):
    messages = []
    monkeypatch.setattr("app.anomaly.notifications.send_sms", lambda phone, text: messages.append(text) or True)
    return messages


def leak_sms(messages):
    return [m for m in messages if "above your usual" in m]


def confirm(c, customer_id, value):
    return c.post("/confirm-reading", json={
        "customer_id": customer_id, "meter_id": METER, "confirmed_reading": f"{value:.3f}",
    }).json()


def test_a_household_should_get_its_own_estimate(household_client, household):
    r = household_client.get(f"/customers/{household[0]}/usage")
    assert r.status_code == 200
    body = r.json()
    assert body["projected_m3"] == 12.0
    assert body["projected_amount"] > 0
    assert body["leak_warning"] is False


def test_when_a_household_asks_for_another_account_should_return_404(db, household_client, household):
    add_household(db, "MTR-OTHER", make_history([0.4] * 4), phone="+250788000999")
    assert household_client.get("/customers/CUST-OTHER/usage").status_code == 404


def test_when_signed_out_should_return_401(anon_client, household):
    assert anon_client.get(f"/customers/{household[0]}/usage").status_code == 401


def test_todays_number_should_change_the_estimate_and_store_nothing(db, household_client, household):
    customer_id, last = household
    before = db.query(Reading).count()
    r = household_client.get(f"/customers/{customer_id}/usage", params={"meter_now": last + 30})
    assert r.status_code == 200
    assert r.json()["used_meter_now"] is True
    assert r.json()["leak_so_far"] is True
    assert db.query(Reading).count() == before


def test_when_todays_number_is_lower_than_the_last_reading_should_say_so(household_client, household):
    r = household_client.get(f"/customers/{household[0]}/usage", params={"meter_now": household[1] - 5})
    assert r.status_code == 422
    assert "lower than your last reading" in r.json()["detail"]


def test_when_a_billed_reading_looks_like_a_leak_should_sms_the_household_once(db, client, household, sent):
    customer_id, last = household
    body = confirm(client, customer_id, last + 20)  # about 0.67 m3 a day: 1.67x, 8 m3 more; billed, not held
    assert body["validation_status"] == "valid"
    assert "sms_household_sent" in body["anomaly"]["actions"]
    assert leak_sms(sent) == ["WASAC: Your water use this period was about 67% above your usual. "
                              "Please check taps, toilets and pipes for leaks. Call 1580 if you need help."]
    assert client.get(f"/customers/{customer_id}/usage").json()["leak_warning"] is True


def test_when_a_billed_reading_is_as_usual_should_send_no_leak_sms(client, household, sent):
    confirm(client, household[0], household[1] + 12)
    assert leak_sms(sent) == []


def test_when_an_officer_accepts_a_held_high_reading_should_send_the_leak_sms(db, client, household, sent):
    customer_id, last = household
    flag_id = confirm(client, customer_id, last + 40)["anomaly"]["flag_id"]  # over 3x usual: held
    assert leak_sms(sent) == []
    r = client.patch(f"/api/anomaly/flags/{flag_id}/resolve", json={"outcome": "accept"})
    assert r.status_code == 200
    assert len(leak_sms(sent)) == 1


def test_when_the_leak_sms_fails_should_still_keep_the_bill(db, client, household, monkeypatch):
    monkeypatch.setattr("app.anomaly.notifications.send_sms", lambda phone, text: False)
    body = confirm(client, household[0], household[1] + 20)
    assert "sms_household_not_sent" in body["anomaly"]["actions"]
    assert db.query(Bill).filter(Bill.bill_id == body["bill_id"]).count() == 1
