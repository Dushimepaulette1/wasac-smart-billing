"""Per-IP rate limits for the public photo endpoints. In memory: right for one API process."""
import logging
import math
import os
import threading
import time
from collections import deque
from typing import Deque, Dict

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
_logged_forwarded = False


def client_ip(request: Request) -> str:
    """The caller's IP. Behind a proxy (Render) every request comes from the proxy,
    so read X-Forwarded-For, counting TRUSTED_PROXY_HOPS entries from the right: those were added
    by proxies we trust, while entries further left can be faked by the client."""
    global _logged_forwarded
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        hops = [h.strip() for h in forwarded.split(",") if h.strip()]
        if not _logged_forwarded:
            _logged_forwarded = True  # once, and never the addresses themselves
            logger.info("X-Forwarded-For has %d entries (TRUSTED_PROXY_HOPS decides which is used)", len(hops))
        trusted = max(1, int(os.getenv("TRUSTED_PROXY_HOPS", "1")))
        if hops:
            return hops[-trusted] if len(hops) >= trusted else hops[0]
    return request.client.host if request.client else "unknown"


class RateLimiter:
    """At most `limit` calls per `window` seconds for each key (sliding window)."""

    MAX_KEYS = 10_000

    def __init__(self, limit: int, window: float):
        self.limit, self.window = limit, window
        self._hits: Dict[str, Deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> float:
        """Record a call. Returns 0 if allowed, else seconds until the next call is allowed."""
        now = time.monotonic()
        with self._lock:
            if len(self._hits) > self.MAX_KEYS:
                self._prune(now)
            hits = self._hits.setdefault(key, deque())
            while hits and now - hits[0] >= self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                return self.window - (now - hits[0])
            hits.append(now)
            return 0.0

    def _prune(self, now: float) -> None:
        for key in [k for k, h in self._hits.items() if not h or now - h[-1] >= self.window]:
            del self._hits[key]

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


MAX_UPLOAD_BYTES = 10 * 1024 * 1024
# Multipart framing around the file; a 10 MB photo must not be refused for its form overhead.
_MULTIPART_SLACK = 64 * 1024

# path -> (limiter, message)
LIMITS = {
    "/guide-frame": (RateLimiter(limit=3, window=1.0),
                     "Too many live checks. Live tips will pause; you can still take the photo."),
    "/submit-photo": (RateLimiter(limit=10, window=60.0),
                      "Too many photos in a short time. Wait a minute, then try again."),
    # The check before sending a reading: a person checks a few times; more is probing values.
    "/check-reading": (RateLimiter(limit=20, window=60.0),
                       "Too many checks in a short time. Wait a minute, then try again."),
}


def reset_limits() -> None:
    for limiter, _ in LIMITS.values():
        limiter.reset()


async def upload_guard(request: Request, call_next):
    """HTTP middleware for the photo endpoints: refuse oversized uploads (413) and callers over
    their rate limit (429) before the body is read, so neither costs bandwidth or disk."""
    rule = LIMITS.get(request.url.path)
    if rule is None or request.method != "POST":
        return await call_next(request)
    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > MAX_UPLOAD_BYTES + _MULTIPART_SLACK:
        return JSONResponse(status_code=413, content={"detail": "Image larger than 10 MB"})
    limiter, message = rule
    wait = limiter.check(client_ip(request))
    if wait:
        return JSONResponse(status_code=429, content={"detail": message},
                            headers={"Retry-After": str(max(1, math.ceil(wait)))})
    return await call_next(request)
