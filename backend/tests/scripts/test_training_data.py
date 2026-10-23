"""Training histories read from the database (scripts/_data.py)."""
from datetime import datetime, timedelta

from app.models import Reading


def test_when_reading_histories_from_the_database_should_leave_out_held_and_rejected_readings(db, monkeypatch):
    import app.db.session as session
    from scripts import _data

    start = datetime(2026, 1, 1)
    for i, (value, status) in enumerate([(10.0, "valid"), (900.0, "pending_review"), (5.0, "rejected"),
                                         (20.0, "anomaly_flagged")]):
        db.add(Reading(meter_id="MTR-T", submitted_value=value, validation_status=status,
                       submission_time=start + timedelta(days=30 * i)))
    db.commit()
    monkeypatch.setattr(session, "SessionLocal", lambda: db)
    monkeypatch.setattr(db, "close", lambda: None)

    history = _data.load_histories_db()["MTR-T"]
    assert [p.reading_m3 for p in history] == [10.0, 20.0]
