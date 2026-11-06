"""Expired images are removed without waiting for another household to upload a photo."""
import asyncio
from datetime import datetime, timedelta

from app.db import session
from app.models import PhotoRead
from app.services import maintenance


def test_cleanup_job_should_commit_expired_photo_deletion(db, monkeypatch):
    db.add(PhotoRead(id="old", owner="test", created_at=datetime.utcnow() - timedelta(days=2), image_jpeg=b"x"))
    db.commit()
    monkeypatch.setattr(session, "SessionLocal", lambda: db)
    maintenance.clean_expired_photos()
    assert db.get(PhotoRead, "old") is None


def test_cleanup_loop_should_run_at_startup_and_retry_after_a_failure(monkeypatch):
    calls = []

    def cleanup():
        calls.append("cleanup")
        if calls.count("cleanup") == 1:
            raise RuntimeError("database temporarily unavailable")

    async def sleep(seconds):
        calls.append(seconds)
        if calls.count("cleanup") == 2:
            raise asyncio.CancelledError()

    monkeypatch.setattr(maintenance, "clean_expired_photos", cleanup)
    monkeypatch.setattr(maintenance.asyncio, "sleep", sleep)
    try:
        asyncio.run(maintenance.clean_photos_periodically())
    except asyncio.CancelledError:
        pass
    assert calls == ["cleanup", 3600, "cleanup", 3600]
