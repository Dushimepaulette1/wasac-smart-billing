from datetime import timedelta
from statistics import median

from conftest import add_household

from anomaly.features import build_periods
from anomaly.readings import m3_to_digits
from database import Bill, Meter, Reading

DEMO_ID = "DEMO-MTR-002"


def _spike_digits(points, config, factor=5):
    daily = median(p.daily_consumption for p in build_periods(points))
    return m3_to_digits(points[-1].reading_m3 + daily * factor * 30, config)


def test_score_endpoint_flags_and_lists_and_resolves(client, db, config, demo_histories, trained_model_on_disk):
    points = demo_histories[DEMO_ID]
    add_household(db, DEMO_ID, points)
    when = (points[-1].date + timedelta(days=30)).isoformat()

    r = client.post("/api/anomaly/score", json={
        "household_id": DEMO_ID, "reading_digits": _spike_digits(points, config), "reading_date": when,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["anomaly_type"] == "SPIKE"
    assert "sms_household_logged" in body["actions"] and "staff_dashboard_flag" in body["actions"]

    flags = client.get("/api/anomaly/flags", params={"household_id": DEMO_ID, "status": "open"}).json()
    assert [f["id"] for f in flags] == [body["flag_id"]]

    resolved = client.patch(f"/api/anomaly/flags/{body['flag_id']}/resolve").json()
    assert resolved["status"] == "resolved" and resolved["resolved_at"]
    assert client.get("/api/anomaly/flags", params={"status": "open"}).json() == []


def test_score_endpoint_unknown_household_404(client):
    r = client.post("/api/anomaly/score", json={"household_id": "NOPE", "reading_digits": "00565846"})
    assert r.status_code == 404


def test_resolve_unknown_flag_404(client):
    assert client.patch("/api/anomaly/flags/999/resolve").status_code == 404


def test_flags_rejects_bad_status_filter(client):
    assert client.get("/api/anomaly/flags", params={"status": "closed"}).status_code == 422


def test_confirm_reading_keeps_behaviour_and_adds_anomaly(client, db, demo_histories):
    points = demo_histories[DEMO_ID]
    customer_id = add_household(db, DEMO_ID, points)
    daily = median(p.daily_consumption for p in build_periods(points))
    # Scored "now", long after the demo history ends, so per-day use is tiny: rules-only, no model on disk.
    submitted = round(points[-1].reading_m3 + daily * 30, 3)

    r = client.post("/confirm-reading", json={
        "customer_id": customer_id, "meter_id": DEMO_ID, "confirmed_reading": str(submitted),
    })
    assert r.status_code == 200
    body = r.json()
    assert body["success"] and body["bill_id"] and body["tariff_breakdown"]
    assert body["validation_status"] == "valid" and body["anomaly_flagged"] is False
    assert body["anomaly"]["anomaly_type"] == "NORMAL"

    stored = db.get(Reading, db.get(Bill, body["bill_id"]).reading_id)
    assert stored.validation_status == "valid" and stored.anomaly_score == 0.0
    assert db.get(Meter, DEMO_ID).last_reading == submitted


def test_confirm_reading_spike_sets_anomaly_flagged(client, db, demo_histories):
    points = demo_histories[DEMO_ID]
    customer_id = add_household(db, DEMO_ID, points)
    huge = round(points[-1].reading_m3 + 100000, 3)  # far above 5 m3/day whatever the gap
    body = client.post("/confirm-reading", json={
        "customer_id": customer_id, "meter_id": DEMO_ID, "confirmed_reading": str(huge),
    }).json()
    assert body["validation_status"] == "anomaly_flagged" and body["anomaly_flagged"]
    assert body["anomaly"]["anomaly_type"] == "SPIKE" and body["anomaly"]["flag_id"]


def test_confirm_reading_still_rejects_backwards(client, db, demo_histories):
    points = demo_histories[DEMO_ID]
    customer_id = add_household(db, DEMO_ID, points)
    body = client.post("/confirm-reading", json={
        "customer_id": customer_id, "meter_id": DEMO_ID, "confirmed_reading": str(points[-1].reading_m3 - 1),
    }).json()
    assert body["success"] is False and body["validation_status"] == "rejected"


def test_ussd_includes_anomaly_and_message(client, db, demo_histories):
    points = demo_histories[DEMO_ID]
    add_household(db, DEMO_ID, points, phone="+250788999000")
    huge = points[-1].reading_m3 + 100000
    body = client.post("/submit-ussd", json={"phone_number": "+250788999000", "reading_value": str(huge)}).json()
    assert body["response"].startswith("END Reading received")
    assert "leaks" in body["response"]
    assert body["anomaly"]["anomaly_type"] == "SPIKE"
