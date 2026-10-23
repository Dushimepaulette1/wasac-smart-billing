"""The health check (app/api/routes/health.py)."""


def test_when_health_is_checked_should_report_each_model(anon_client):
    from app.vision.models import registry as live

    body = anon_client.get("/health").json()
    assert body["photo_reading"] in ("ready", "manual_entry_only")
    assert body["yolo_model"] == live.status["yolo"].label()


def test_when_health_is_checked_should_report_peak_memory(anon_client):
    assert anon_client.get("/health").json()["memory_peak_mb"] > 0


def test_when_the_database_cannot_be_reached_should_say_degraded_and_not_ready(anon_client, monkeypatch):
    from app.api.routes import health

    def broken():
        raise RuntimeError("no database")

    monkeypatch.setattr(health, "SessionLocal", broken)
    body = anon_client.get("/health")
    assert body.status_code == 200 and body.json()["status"] == "degraded" and body.json()["database"] == "disconnected"
    ready = anon_client.get("/health/ready")
    assert ready.status_code == 503 and ready.json()["status"] == "unavailable"


def test_when_the_database_answers_should_be_ready(anon_client, monkeypatch):
    from contextlib import nullcontext
    from app.api.routes import health

    class FakeSession:
        def execute(self, _):
            return None

    monkeypatch.setattr(health, "SessionLocal", lambda: nullcontext(FakeSession()))
    assert anon_client.get("/health/ready").status_code == 200
    assert anon_client.get("/health").json()["status"] == "ok"
