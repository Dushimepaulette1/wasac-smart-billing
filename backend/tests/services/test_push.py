"""Phone alerts, web push (app/services/push.py, app/api/routes/push.py)."""
import json

import pytest

from app.models import PushSubscription
from app.services import push

PHONE = "+250788000111"  # household_client's phone
SUB = {"endpoint": "https://push.example.org/send/abc123", "keys": {"p256dh": "B" * 87, "auth": "a" * 22}}


@pytest.fixture
def household(db):
    from support.factories import add_household, make_history

    return add_household(db, "MTR-P", make_history([0.4] * 3), phone=PHONE)


@pytest.fixture
def keys(monkeypatch):
    monkeypatch.setenv("VAPID_PUBLIC_KEY", "PUBLICKEY")
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "PRIVATEKEY")


def test_when_alerts_are_not_set_up_should_say_so_and_store_nothing(household_client, db, household, monkeypatch):
    monkeypatch.delenv("VAPID_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("VAPID_PRIVATE_KEY", raising=False)
    assert household_client.get("/household/push/key").status_code == 404
    assert household_client.post("/household/push/subscribe", json=SUB).status_code == 404
    assert db.query(PushSubscription).count() == 0


def test_when_a_household_turns_alerts_on_should_keep_the_subscription_for_its_phone(household_client, db, household, keys):
    assert household_client.get("/household/push/key").json() == {"public_key": "PUBLICKEY"}
    assert household_client.post("/household/push/subscribe", json=SUB).status_code == 204
    assert household_client.post("/household/push/subscribe", json=SUB).status_code == 204  # again: one row
    rows = db.query(PushSubscription).all()
    assert [(r.phone, r.endpoint) for r in rows] == [(PHONE, SUB["endpoint"])]

    assert household_client.post("/household/push/unsubscribe", json={"endpoint": SUB["endpoint"]}).status_code == 204
    assert db.query(PushSubscription).count() == 0


def test_when_a_subscription_is_not_https_or_from_staff_should_refuse_it(household_client, client, household, keys):
    bad = {**SUB, "endpoint": "http://push.example.org/x123456"}
    assert household_client.post("/household/push/subscribe", json=bad).status_code == 422
    assert client.post("/household/push/subscribe", json=SUB).status_code == 400


def test_when_sending_should_encrypt_to_each_browser_and_drop_ones_that_are_gone(db, keys, monkeypatch):
    import pywebpush

    db.add_all([
        PushSubscription(phone=PHONE, endpoint="https://push.example.org/live", p256dh="p", auth="a"),
        PushSubscription(phone=PHONE, endpoint="https://push.example.org/gone", p256dh="p", auth="a"),
        PushSubscription(phone="+250788999999", endpoint="https://push.example.org/other", p256dh="p", auth="a"),
    ])
    db.commit()
    calls = []

    class Gone:
        status_code = 410

    def fake_webpush(info, data, **kwargs):
        calls.append((info["endpoint"], json.loads(data), kwargs["vapid_private_key"]))
        if info["endpoint"].endswith("gone"):
            raise pywebpush.WebPushException("gone", response=Gone())

    monkeypatch.setattr(pywebpush, "webpush", fake_webpush)
    assert push.send_to_phone(db, PHONE, "Mubazi", "Accepted", "/history") == 1
    assert sorted(c[0] for c in calls) == ["https://push.example.org/gone", "https://push.example.org/live"]
    assert calls[0][1] == {"title": "Mubazi", "body": "Accepted", "url": "/history", "tag": "mubazi-decision"}
    assert calls[0][2] == "PRIVATEKEY"
    assert {r.endpoint for r in db.query(PushSubscription).all()} == {
        "https://push.example.org/live", "https://push.example.org/other"}


def test_when_an_officer_decides_should_alert_the_households_phone(client, db, monkeypatch):
    from datetime import datetime, timedelta
    from app.anomaly import review
    from support.factories import add_household, make_history

    sent = []
    monkeypatch.setattr(review, "send_to_phone", lambda db, phone, title, body, url: sent.append((phone, title, url)) or 1)
    start = datetime.utcnow() - timedelta(days=30 * 9)
    points = make_history([0.4] * 8, start=start)
    customer_id = add_household(db, "MTR-A", points, phone=PHONE)
    held = client.post("/confirm-reading", json={
        "customer_id": customer_id, "meter_id": "MTR-A", "confirmed_reading": str(round(points[-1].reading_m3 + 200, 3)),
    }).json()
    body = client.patch(f"/api/anomaly/flags/{held['anomaly']['flag_id']}/resolve", json={"outcome": "accept"}).json()
    assert sent == [(PHONE, "Mubazi: igipimo cyemejwe", "/history")]
    assert "push_household_sent" in body["actions"]


def test_when_making_the_alert_text_should_say_the_amount_in_both_languages():
    from app.anomaly.review import decision_alert

    title, body, url = decision_alert("accept", 12400.4)
    assert "RWF 12,400" in body and "Your reading was accepted" in body and url == "/history"
    assert decision_alert("reject", None)[2] == "/submit/camera"
