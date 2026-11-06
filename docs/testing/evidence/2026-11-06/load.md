# Load test (local)

Made by `tools/load/local_load.py` on 2026-11-06: 300 requests per row, one API worker, SQLite, on a laptop.
Not run on the live free servers. Photo reading is timed separately (`backend/scripts/benchmark_vision.py`).

| Endpoint | Concurrent users | Requests/s | Median (ms) | 95th percentile (ms) | Errors |
|---|---|---|---|---|---|
| GET /health | 1 | 1307 | 1 | 1 | 0 |
| GET /health | 10 | 1358 | 5 | 12 | 0 |
| GET /health | 50 | 1867 | 24 | 38 | 0 |
| POST /calculate-bill | 1 | 1673 | 0 | 1 | 0 |
| POST /calculate-bill | 10 | 3096 | 3 | 3 | 0 |
| POST /calculate-bill | 50 | 3101 | 16 | 16 | 0 |

