"""The health check (app/api/routes/health.py)."""


def test_when_health_is_checked_should_report_each_model(anon_client):
    from app.vision.models import registry as live

    body = anon_client.get("/health").json()
    assert body["photo_reading"] in ("ready", "manual_entry_only")
    assert body["yolo_model"] == live.status["yolo"].label()


def test_when_health_is_checked_should_report_peak_memory(anon_client):
    assert anon_client.get("/health").json()["memory_peak_mb"] > 0
