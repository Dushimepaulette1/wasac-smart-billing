"""Settings and protections for the public deployment: rate limits, upload size, CORS, seeding."""
import importlib

import pytest
from starlette.requests import Request

import ratelimit
from ratelimit import RateLimiter, client_ip


@pytest.fixture(autouse=True)
def fresh_limits():
    ratelimit.reset_limits()
    yield
    ratelimit.reset_limits()


def _request(headers=None, host="10.0.0.1"):
    raw = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    return Request({"type": "http", "headers": raw, "client": (host, 1234)})


def test_limiter_allows_the_limit_then_reports_the_wait():
    limiter = RateLimiter(limit=3, window=1.0)
    assert [limiter.check("a") for _ in range(3)] == [0.0, 0.0, 0.0]
    assert 0 < limiter.check("a") <= 1.0
    assert limiter.check("b") == 0.0  # per caller


def test_client_ip_uses_the_proxy_added_entry_not_a_spoofed_one(monkeypatch):
    monkeypatch.delenv("TRUSTED_PROXY_HOPS", raising=False)
    assert client_ip(_request({"X-Forwarded-For": "6.6.6.6, 41.186.0.9"})) == "41.186.0.9"
    monkeypatch.setenv("TRUSTED_PROXY_HOPS", "2")
    assert client_ip(_request({"X-Forwarded-For": "6.6.6.6, 41.186.0.9, 10.1.1.1"})) == "41.186.0.9"
    assert client_ip(_request()) == "10.0.0.1"


def _frame():
    import cv2
    import numpy as np

    return cv2.imencode(".jpg", np.full((48, 64, 3), 128, np.uint8))[1].tobytes()


def test_guide_frame_allows_three_per_second_then_429(client):
    codes = [client.post("/guide-frame", files={"file": ("f.jpg", _frame(), "image/jpeg")}).status_code
             for _ in range(4)]
    assert codes[:3] == [200, 200, 200] and codes[3] == 429
    r = client.post("/guide-frame", files={"file": ("f.jpg", _frame(), "image/jpeg")})
    assert r.status_code == 429 and "Live tips will pause" in r.json()["detail"]
    assert int(r.headers["retry-after"]) >= 1


def test_submit_photo_allows_ten_per_minute(client):
    codes = [client.post("/submit-photo", files={"file": ("p.jpg", _frame(), "image/jpeg")}).status_code
             for _ in range(11)]
    assert 429 not in codes[:10] and codes[10] == 429


def test_oversized_upload_is_refused_before_it_is_read(client):
    big = b"\xff" * (10 * 1024 * 1024 + 200 * 1024)
    r = client.post("/submit-photo", files={"file": ("p.jpg", big, "image/jpeg")})
    assert r.status_code == 413 and "10 MB" in r.json()["detail"]


def test_refusals_carry_cors_headers_so_the_app_can_show_them(client):
    origin = {"Origin": "http://localhost:3000"}
    for _ in range(3):
        client.post("/guide-frame", files={"file": ("f.jpg", _frame(), "image/jpeg")}, headers=origin)
    r = client.post("/guide-frame", files={"file": ("f.jpg", _frame(), "image/jpeg")}, headers=origin)
    assert r.status_code == 429
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_cors_origins_come_from_the_environment(monkeypatch):
    import main

    monkeypatch.setenv("CORS_ORIGINS", "https://wasac.vercel.app/, https://example.org")
    assert main._cors_origins() == ["https://wasac.vercel.app", "https://example.org"]
    monkeypatch.delenv("CORS_ORIGINS")
    assert main._cors_origins() == ["http://localhost:3000", "http://127.0.0.1:3000"]


def test_sample_seed_can_be_turned_off(monkeypatch):
    import database

    calls = []
    monkeypatch.setattr(database.Base.metadata, "create_all", lambda bind: None)
    monkeypatch.setattr(database, "seed_data", lambda: calls.append(1))
    monkeypatch.setenv("SEED_SAMPLE_DATA", "0")
    database.init_db()
    assert calls == []
    monkeypatch.setenv("SEED_SAMPLE_DATA", "1")
    database.init_db()
    assert calls == [1]


def test_health_reports_peak_memory(anon_client):
    assert anon_client.get("/health").json()["memory_peak_mb"] > 0
