"""Rate limits, upload size limits and the caller's IP (app/core/ratelimit.py)."""
from starlette.requests import Request
from app.core.ratelimit import RateLimiter, client_ip


def _request(headers=None, host="10.0.0.1"):
    raw = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    return Request({"type": "http", "headers": raw, "client": (host, 1234)})


def test_when_the_limit_is_reached_should_report_the_wait():
    limiter = RateLimiter(limit=3, window=1.0)
    assert [limiter.check("a") for _ in range(3)] == [0.0, 0.0, 0.0]
    assert 0 < limiter.check("a") <= 1.0
    assert limiter.check("b") == 0.0  # per caller


def test_when_behind_a_proxy_should_use_its_entry_not_a_spoofed_one(monkeypatch):
    monkeypatch.delenv("TRUSTED_PROXY_HOPS", raising=False)
    assert client_ip(_request({"X-Forwarded-For": "6.6.6.6, 41.186.0.9"})) == "41.186.0.9"
    monkeypatch.setenv("TRUSTED_PROXY_HOPS", "2")
    assert client_ip(_request({"X-Forwarded-For": "6.6.6.6, 41.186.0.9, 10.1.1.1"})) == "41.186.0.9"
    assert client_ip(_request()) == "10.0.0.1"


def _frame():
    import cv2
    import numpy as np

    return cv2.imencode(".jpg", np.full((48, 64, 3), 128, np.uint8))[1].tobytes()


def test_when_live_tips_exceed_three_per_second_should_return_429(client):
    codes = [client.post("/guide-frame", files={"file": ("f.jpg", _frame(), "image/jpeg")}).status_code
             for _ in range(4)]
    assert codes[:3] == [200, 200, 200] and codes[3] == 429
    r = client.post("/guide-frame", files={"file": ("f.jpg", _frame(), "image/jpeg")})
    assert r.status_code == 429 and "Live tips will pause" in r.json()["detail"]
    assert int(r.headers["retry-after"]) >= 1


def test_when_photos_exceed_ten_per_minute_should_return_429(client):
    codes = [client.post("/submit-photo", files={"file": ("p.jpg", _frame(), "image/jpeg")}).status_code
             for _ in range(11)]
    assert 429 not in codes[:10] and codes[10] == 429


def test_when_an_upload_is_over_10_mb_should_refuse_it_before_reading_it(client):
    big = b"\xff" * (10 * 1024 * 1024 + 200 * 1024)
    r = client.post("/submit-photo", files={"file": ("p.jpg", big, "image/jpeg")})
    assert r.status_code == 413 and "10 MB" in r.json()["detail"]


def test_when_a_request_is_refused_should_still_carry_cors_headers(client):
    origin = {"Origin": "http://localhost:3000"}
    for _ in range(3):
        client.post("/guide-frame", files={"file": ("f.jpg", _frame(), "image/jpeg")}, headers=origin)
    r = client.post("/guide-frame", files={"file": ("f.jpg", _frame(), "image/jpeg")}, headers=origin)
    assert r.status_code == 429
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"
