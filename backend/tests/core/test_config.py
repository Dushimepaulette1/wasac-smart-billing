"""Settings from the environment (app/core/config.py) and the sample-data switch (app/db/init_db.py)."""


def test_when_cors_origins_is_set_should_use_those_origins(monkeypatch):
    from app.core.config import cors_origins

    monkeypatch.setenv("CORS_ORIGINS", "https://wasac.vercel.app/, https://example.org")
    assert cors_origins() == ["https://wasac.vercel.app", "https://example.org"]
    monkeypatch.delenv("CORS_ORIGINS")
    assert cors_origins() == ["http://localhost:3000", "http://127.0.0.1:3000"]


def test_when_seed_sample_data_is_0_should_not_create_samples(monkeypatch):
    from app.db import init_db, seed, session

    calls = []
    monkeypatch.setattr(session.Base.metadata, "create_all", lambda bind: None)
    monkeypatch.setattr(seed, "seed_data", lambda: calls.append(1))
    monkeypatch.setenv("SEED_SAMPLE_DATA", "0")
    init_db.init_db()
    assert calls == []
    monkeypatch.setenv("SEED_SAMPLE_DATA", "1")
    init_db.init_db()
    assert calls == [1]
