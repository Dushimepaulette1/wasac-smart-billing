"""Stress test of a local API. Writes docs/testing/load.md. Never point this at the live servers.

    python tools/load/local_load.py http://localhost:8000

Each endpoint gets the same number of requests at rising concurrency; slowest-case times and errors
show where it starts to struggle. SQLite on one worker, so treat the numbers as a lower bound.
"""
import json
import statistics
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

API = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
if urlparse(API).hostname not in ("localhost", "127.0.0.1"):
    sys.exit("Local servers only: this sends a lot of requests.")

REQUESTS = 300
ENDPOINTS = [
    ("GET /health", "/health", None),
    ("POST /calculate-bill", "/calculate-bill", {"consumption_m3": 18.5}),
]


def call(path, body):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(API + path, data, {"content-type": "application/json"})
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response.read()
            ok = response.status == 200
    except (urllib.error.URLError, TimeoutError):
        ok = False
    return (time.perf_counter() - started) * 1000, ok


rows = []
for label, path, body in ENDPOINTS:
    for workers in (1, 10, 50):
        started = time.perf_counter()
        with ThreadPoolExecutor(workers) as pool:
            results = list(pool.map(lambda _: call(path, body), range(REQUESTS)))
        seconds = time.perf_counter() - started
        times = sorted(t for t, _ in results)
        errors = sum(1 for _, ok in results if not ok)
        p95 = times[int(len(times) * 0.95) - 1]
        rows.append(f"| {label} | {workers} | {REQUESTS / seconds:.0f} | {statistics.median(times):.0f} | {p95:.0f} | {errors} |")

report = f"""# Load test (local)

Made by `tools/load/local_load.py` on {date.today()}: {REQUESTS} requests per row, one API worker, SQLite, on a laptop.
Not run on the live free servers. Photo reading is timed separately (`backend/scripts/benchmark_vision.py`).

| Endpoint | Concurrent users | Requests/s | Median (ms) | 95th percentile (ms) | Errors |
|---|---|---|---|---|---|
""" + "\n".join(rows) + "\n"
Path(__file__).resolve().parents[2].joinpath("docs/testing/load.md").write_text(report)
print(report)
