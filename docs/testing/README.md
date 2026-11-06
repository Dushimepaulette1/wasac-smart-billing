# Testing summary

## Latest local validation — 6 November 2026

The current working tree passed **617 backend tests (5 skipped)** and **262 frontend tests**:
**879 passed in total**, including **16 PostgreSQL concurrency/migration checks**. Backend line
coverage is **94.10%** and frontend **83.36%**. TypeScript checking and the production build passed.
The negative-control payment race was made deterministic after a local run exposed its timing assumption.
The model-downloader secrecy test now explicitly selects .pt format, so the production image's ONNX default does not change its test scenario.

Environment: macOS, Python **3.9.6**, Node **22.23.4**, PostgreSQL **16** in a local Docker container.
The downloaded Mac Python 3.10 executable was killed when started. A subsequent build of the actual
production image and full suite on **Linux Python 3.10.22** passed **617 tests, 5 skipped**, with
94% line coverage. The supported Python 3.10 GitHub CI workflow must also pass on the submitted commit. Tests used isolated
SQLite/PostgreSQL databases and fake providers, never Neon or real money/SMS.

A PostgreSQL 16 dump/restore drill preserved all table counts, 40 synthetic customers, 960 readings,
revision 0002, a RWF 1,000 bill and a RWF 500 successful payment. A local endpoint load test again
reported zero errors at concurrency 1, 10 and 50. Neither is a real customer or production recovery test.

Dated outputs are in [evidence/2026-11-06](evidence/2026-11-06/).
Fresh **36/36** browser checks passed in the official Linux Playwright 1.56.1 container (Chromium
141.0.7390.37, Firefox 142.0.1, WebKit 26.0). The **25-step local journey passed with zero reported
problems**, including acceptance, simulated payment confirmation and rejection. The app was served
from its production frontend build against a local SQLite API with synthetic data. Private model
weights were absent: the journey verifies manual-entry fallback, not recognition accuracy or real
provider delivery. An outdated demo-code text selector was repaired during this run. A final regression test confirms
that a stale sector link cannot silently select a different household's reading.

Mac browser launch attempts failed; Linux Docker supplied the successful run. Slow network/CPU and
screen sizes are simulations, not real phones. Fresh landing-page first contentful paint was 60 ms
unthrottled, 1,068 ms on simulated fast 3G and 3,388 ms on slow 3G. The older live journey and Ubuntu
results below remain historical evidence. No current live accounts were modified.

## Metric interpretation and submitted CI

The notebook's 55.7% reading measure strips leading zeros before comparison. Strict eight-character
exact match and individual-digit accuracy are different metrics; the report labels this explicitly.
Public GitHub CI for commit `6109b4f` succeeded in
[run 42252023480](https://github.com/Dushimepaulette1/wasac-smart-billing/actions/runs/42252023480).
Report and submission-packaging corrections after that commit require their own final CI run.

## Historical evidence

| Strategy | Why it was chosen | How | Result | What it changed |
|---|---|---|---|---|
| Unit and integration | Billing, payments and rules must be right every time | pytest (in-memory database, fake models), Vitest and React Testing Library, on every push in GitHub Actions | 569 backend passed, 5 skipped (the 14 PostgreSQL race tests run only in CI); 233 frontend passed. Coverage: backend 94%, frontend 83% of lines (CI run 41227686801) | Three payment bugs and two reading bugs fixed; see the last section |
| Concurrency | Two taps or two officers must not charge or bill twice, and SQLite cannot show this | `backend/tests/pg/test_concurrency.py` on PostgreSQL 16 in CI, with a control test showing the race is real without the guards | Passed in CI | Row locks, partial unique indexes and idempotency keys on readings, reviews and payments |
| End-to-end functional | Only a real browser proves the layers work together | `tools/e2e/live_e2e.mjs`: household and officer, reading to bill to payment, plus a rejected reading | Live site 25/25 steps, 0 problems, on the merged code (households 027 and 028, 31 Oct 2026) | Kept in `tools/e2e` as a repeatable check; it grew from 18 to 25 steps as features were added |
| Model evaluation | Accuracy must be measured on meters the model never saw | Locked test set split by meter, used once | 55.7% reading accuracy (95% CI 42 to 69%), 70.9% right or within one digit | Every reading is confirmed by the household; the quality gate advises and never blocks |
| Compatibility | Households use many phones and browsers | `tools/e2e/compat_check.mjs` on Chromium, Firefox and WebKit at four sizes, in CI; a manual test on a real phone | 36 of 36 passed (see below) | Added to CI, so every pull request is checked on all three engines |
| Performance and stress | Slow phones, slow data and free servers | Simulated 3G and slow CPU, `tools/load/local_load.py`, deployed timings | No errors at 50 concurrent users locally (see below); 1.3 to 3.7 s to read a photo on the free server | Models moved from PyTorch to ONNX Runtime, because PyTorch did not fit the 512 MB server |

## Different inputs and how the system responds

| Input | Expected behaviour | Tested in |
|---|---|---|
| Normal reading | Billed at once | `tests/api/test_reading_check.py` |
| Reading below the last one | Held for an officer, not billed | `tests/anomaly/test_household_edits.py` |
| About 3x usual use, or 10x (a shifted digit) | Held, explained | `tests/anomaly/test_history_rule.py` |
| First reading with no starting value | Held; becomes the start, no bill | `tests/anomaly/test_no_baseline.py` |
| Value typed 1 m³ or more below a reliable AI read | Held, officer sees the changed wheels | `tests/anomaly/test_household_edits.py` |
| Meter passing 99,999 | Held, billed across the wrap | `tests/anomaly/test_rollover.py` |
| Second reading within 25 days, or the same value twice | Refused with the reason | `tests/services/test_reading_window.py`, `tests/anomaly/test_evaluate_reading.py` |
| Same photo sent twice | Returns the first result | `tests/api/test_reading_check.py` |
| Unregistered phone, wrong code | Clear message, limits on tries | `tests/api/test_household_auth.py` |
| Malformed or reused transaction ID | Refused | `tests/services/test_payments.py`, `tests/api/test_ussd.py` |
| CSV with bad rows, repeated meters, missing columns | Preview lists each row; nothing saved | `tests/services/test_households.py` |
| MTN timeout, 5xx or 404 | Attempt stays open, never a second prompt | `tests/services/test_payments.py` |
| Bill correction by the person who asked for it | Refused: needs a second person | `tests/services/test_bill_corrections.py` |

## Software and hardware covered

| Environment | Tested | How |
|---|---|---|
| Browser engines | Chromium 141, Firefox 142, WebKit 26 on Ubuntu; Chrome 156 on macOS | Real browsers, by `tools/e2e/compat_check.mjs` |
| Operating system | Ubuntu (CI runners); macOS 27.2 (Apple M5, 24 GB); the author's phone | Windows and Android were not measured |
| Screen sizes | 360x640, 390x844, 768x1024, 1366x768 | Simulated in the browser |
| Low-end device | 4x slower CPU on fast and slow 3G | Simulated, not a real low-cost phone |
| No slowdown | No limits on network or CPU, on a CI runner | Automated, as the comparison for the row above. No high-end phone was measured |
| Server | 512 MB free instance, peak memory 274 MB | Render free plan |

Frames per second is not reported. The app is ordinary web pages with no game or graphics loop, so first paint, download
size and server memory are the measures that matter. The closest thing to a frame rate is the live camera tip, which takes
about 0.7 s per frame on the deployed server.

## Compatibility

`tools/e2e/compat_check.mjs` loaded 3 pages at 4 screen sizes (360x640 to 1366x768) on the production build, in GitHub
Actions on 31 October 2026. Each page had to load, show its heading, and have no sideways scroll or page errors.

| Browser engine | Passed | Page load |
|---|---|---|
| Chromium 141.0.7390.37 | 12 of 12 | 96 to 188 ms |
| Firefox 142.0.1 | 12 of 12 | 146 to 425 ms |
| WebKit 26.0 | 12 of 12 | 233 to 646 ms |

These are real browser engines at simulated screen sizes. WebKit stands in for Safari but is not Safari on an iPhone.

On macOS 27.2, Chrome 156 passed the same 12 of 12 checks, with pages loading in 41 to 228 ms.

## Page speed

Landing page at phone size, with no cache. The network and CPU limits are simulated.

| Conditions | First paint | Downloaded |
|---|---|---|
| No limit | 168 ms | 194 KB |
| Fast 3G, 4x slower CPU | 1,228 ms | 194 KB |
| Slow 3G, 4x slower CPU | 3,516 ms | 123 KB |

The same test on macOS gave 56 ms with no limit, 1,040 ms on fast 3G and 3,328 ms on slow 3G, with the same simulated limits.

## Load test

`tools/load/local_load.py` sent 300 requests per row to one local API worker with SQLite. It never runs on the live servers.

| Endpoint | Users at once | Requests/s | Median | 95th percentile | Errors |
|---|---|---|---|---|---|
| GET /health | 1 | 263 | 3 ms | 6 ms | 0 |
| GET /health | 10 | 198 | 43 ms | 67 ms | 0 |
| GET /health | 50 | 228 | 213 ms | 245 ms | 0 |
| POST /calculate-bill | 1 | 341 | 3 ms | 4 ms | 0 |
| POST /calculate-bill | 10 | 316 | 29 ms | 47 ms | 0 |
| POST /calculate-bill | 50 | 324 | 143 ms | 189 ms | 0 |

## Real phone

The author tested the household and staff journeys by hand on one phone over Wi-Fi and found no problems. Android was not
tried, and timings were not recorded on the phone. The timings on this page come from the automated and simulated runs.

## What testing changed

- A review reproduced three payment bugs: an abandoned MoMo Pay attempt blocked corrections forever, kept credit from being
  used, and a top-up after a correction looked like a double payment with no receipt. Each got a failing test, then a fix
  (`tests/services/test_unclaimed_payments.py`). Basic phones also gained a USSD step for the transaction ID.
- A meter added with no first reading billed the whole register. It is now held (`test_no_baseline.py`).
- Readings at 3 to 10 times normal use were billed because the check only ran inside the undeployed model. It is now a rule.
- Blur checking was turned off after calibration showed it fired more on readable photos.
