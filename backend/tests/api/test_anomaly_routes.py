"""Scoring, flags and the officers' review queue (app/api/routes/anomaly.py)."""
from datetime import timedelta
from statistics import median
from app.anomaly.features import build_periods
from app.anomaly.readings import m3_to_digits
from support.factories import add_household, make_history


DEMO_ID = "DEMO-MTR-002"


def _spike_digits(points, config, factor=5):
    daily = median(p.daily_consumption for p in build_periods(points))
    return m3_to_digits(points[-1].reading_m3 + daily * factor * 30, config)


def test_when_staff_score_a_spike_should_flag_list_and_resolve_it(client, db, config, demo_histories, trained_model_on_disk):
    points = demo_histories[DEMO_ID]
    add_household(db, DEMO_ID, points)
    when = (points[-1].date + timedelta(days=30)).isoformat()

    r = client.post("/api/anomaly/score", json={
        "household_id": DEMO_ID, "reading_digits": _spike_digits(points, config), "reading_date": when,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["anomaly_type"] == "SPIKE"
    assert "sms_household_not_sent" in body["actions"]  # SMS is off in tests and "staff_dashboard_flag" in body["actions"]

    flags = client.get("/api/anomaly/flags", params={"household_id": DEMO_ID, "status": "open"}).json()
    assert [f["id"] for f in flags] == [body["flag_id"]]

    resolved = client.patch(f"/api/anomaly/flags/{body['flag_id']}/resolve").json()
    assert resolved["status"] == "resolved" and resolved["resolved_at"]
    assert client.get("/api/anomaly/flags", params={"status": "open"}).json() == []


def test_when_scoring_an_unknown_household_should_return_404(client):
    r = client.post("/api/anomaly/score", json={"household_id": "NOPE", "reading_digits": "00565846"})
    assert r.status_code == 404


def test_when_resolving_an_unknown_flag_should_return_404(client):
    assert client.patch("/api/anomaly/flags/999/resolve").status_code == 404


def test_when_the_status_filter_is_unknown_should_return_422(client):
    assert client.get("/api/anomaly/flags", params={"status": "closed"}).status_code == 422


def test_when_readings_are_held_should_list_them_in_the_review_queue_with_context(db, client):
    from app.models import AnomalyFlag
    from app.models import Reading

    add_household(db, "MTR-Q", make_history([1.0] * 4))
    reading = Reading(meter_id="MTR-Q", submitted_value=900.0, validation_status="pending_review")
    db.add(reading)
    db.flush()
    db.add(AnomalyFlag(household_id="MTR-Q", reading_id=reading.reading_id, anomaly_type="SPIKE",
                       requires_staff_review=True, status="open"))
    db.commit()
    items = client.get("/api/anomaly/review-queue").json()
    assert len(items) == 1
    assert items[0]["reading_m3"] == 900.0
    assert items[0]["flag"]["anomaly_type"] == "SPIKE"
    assert isinstance(items[0]["history"], list)


def test_when_a_billed_reading_needs_follow_up_should_say_so_and_close_without_an_outcome(db, client):
    from app.models import AnomalyFlag, Reading

    add_household(db, "MTR-F", make_history([1.0] * 4))
    held = Reading(meter_id="MTR-F", submitted_value=900.0, validation_status="pending_review")
    billed = Reading(meter_id="MTR-F", submitted_value=5.0, validation_status="anomaly_flagged")
    db.add_all([held, billed])
    db.flush()
    db.add_all([
        AnomalyFlag(household_id="MTR-F", reading_id=held.reading_id, anomaly_type="SPIKE",
                    requires_staff_review=True, status="open"),
        AnomalyFlag(household_id="MTR-F", reading_id=billed.reading_id, anomaly_type="METER_STUCK",
                    requires_staff_review=True, status="open"),
    ])
    db.commit()
    items = {i["flag"]["anomaly_type"]: i["flag"] for i in client.get("/api/anomaly/review-queue").json()}
    assert items["SPIKE"]["reading_status"] == "pending_review"
    assert items["METER_STUCK"]["reading_status"] == "anomaly_flagged"

    stuck = items["METER_STUCK"]["id"]
    assert client.patch(f"/api/anomaly/flags/{stuck}/resolve", json={"outcome": "accept"}).status_code == 409
    closed = client.patch(f"/api/anomaly/flags/{stuck}/resolve", json={})
    assert closed.status_code == 200 and closed.json()["status"] == "resolved" and closed.json()["outcome"] is None
    assert [i["flag"]["anomaly_type"] for i in client.get("/api/anomaly/review-queue").json()] == ["SPIKE"]


def test_when_a_household_deletes_a_message_should_hide_it_from_them_but_not_from_staff(db, client, household_client):
    from app.models import AnomalyFlag, Reading

    add_household(db, "MTR-M", make_history([1.0] * 4), phone="+250788000111")
    done = Reading(meter_id="MTR-M", submitted_value=5.0, validation_status="valid")
    held = Reading(meter_id="MTR-M", submitted_value=900.0, validation_status="pending_review")
    db.add_all([done, held]); db.flush()
    old = AnomalyFlag(household_id="MTR-M", reading_id=done.reading_id, anomaly_type="SPIKE",
                      requires_staff_review=True, status="resolved")
    waiting = AnomalyFlag(household_id="MTR-M", reading_id=held.reading_id, anomaly_type="SPIKE",
                          requires_staff_review=True, status="open")
    db.add_all([old, waiting]); db.commit()

    assert household_client.delete(f"/api/anomaly/flags/{waiting.id}/message").status_code == 409  # still checking
    assert household_client.delete(f"/api/anomaly/flags/{old.id}/message").status_code == 204
    mine = household_client.get("/api/anomaly/flags", params={"household_id": "MTR-M"}).json()
    assert [f["id"] for f in mine] == [waiting.id]
    staff_view = client.get("/api/anomaly/flags", params={"household_id": "MTR-M"}).json()
    assert {f["id"] for f in staff_view} == {old.id, waiting.id}
    assert household_client.delete("/api/anomaly/flags/999999/message").status_code == 404
