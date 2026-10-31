# Load test (local)

Made by `tools/load/local_load.py` on 2026-10-31: 300 requests per row, one API worker, SQLite, on a laptop.
Not run on the live free servers. Photo reading is timed separately (`backend/scripts/benchmark_vision.py`).

| Endpoint | Concurrent users | Requests/s | Median (ms) | 95th percentile (ms) | Errors |
|---|---|---|---|---|---|
| GET /health | 1 | 263 | 3 | 6 | 0 |
| GET /health | 10 | 198 | 43 | 67 | 0 |
| GET /health | 50 | 228 | 213 | 245 | 0 |
| POST /calculate-bill | 1 | 341 | 3 | 4 | 0 |
| POST /calculate-bill | 10 | 316 | 29 | 47 | 0 |
| POST /calculate-bill | 50 | 324 | 143 | 189 | 0 |
