"""Readings sent through the USSD menu (app/api/routes/ussd.py)."""
from support.factories import add_household


DEMO_ID = "DEMO-MTR-002"


def test_when_a_ussd_reading_is_held_should_say_it_is_being_checked(client, db, demo_histories):
    points = demo_histories[DEMO_ID]
    add_household(db, DEMO_ID, points, phone="+250788999000")
    huge = points[-1].reading_m3 + 100000
    body = client.post("/submit-ussd", json={"phone_number": "+250788999000", "reading_value": str(huge)}).json()
    assert body["response"].startswith("END Reading received")
    assert "being checked" in body["response"] and "Bill:" not in body["response"]
    assert body["anomaly"]["anomaly_type"] == "SPIKE" and body["anomaly"]["pending_review"]


def test_when_a_ussd_reading_is_lower_than_the_last_should_hold_it_not_reject_it(client, db, demo_histories):
    points = demo_histories[DEMO_ID]
    add_household(db, DEMO_ID, points, phone="+250788999000")
    body = client.post("/submit-ussd", json={
        "phone_number": "+250788999000", "reading_value": str(points[-1].reading_m3 - 5),
    }).json()
    assert "being checked" in body["response"]
    assert body["anomaly"]["anomaly_type"] == "MISREAD_SUSPECTED"
