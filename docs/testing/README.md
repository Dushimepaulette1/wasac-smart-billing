# Testing summary

| Strategy | Why it was chosen | How | Result |
|---|---|---|---|
| Unit and integration | Billing, payments and rules must be right every time | pytest (in-memory database, fake models), Vitest and React Testing Library, on every push in GitHub Actions | 569 backend passed, 5 skipped (the 14 PostgreSQL race tests run only in CI); 232 frontend passed. Coverage: backend 94%, frontend 83% of lines (CI run 41227686801) |
| Concurrency | Two taps or two officers must not charge or bill twice, and SQLite cannot show this | `backend/tests/pg/test_concurrency.py` on PostgreSQL 16 in CI, with a control test showing the race is real without the guards | Passed in CI |
| End-to-end functional | Only a real browser proves the layers work together | `tools/e2e/live_e2e.mjs`: household and officer, reading to bill to payment, plus a rejected reading | Live site 25/25 steps, 0 problems, on the merged code (households 027 and 028, 31 Oct 2026) |
| Model evaluation | Accuracy must be measured on meters the model never saw | Locked test set split by meter, used once | 55.7% reading accuracy (95% CI 42 to 69%), 70.9% right or within one digit |
| Compatibility | Households use many phones and browsers | `tools/e2e/compat_check.mjs` on Chromium, Firefox and WebKit at four sizes, in CI; real phones in `real_phone_results.md` | 36 of 36 passed (`compatibility.md`) |
| Performance and stress | Slow phones, slow data and free servers | Simulated 3G and slow CPU, `tools/load/local_load.py`, deployed timings | No errors at 50 concurrent users locally (`load.md`); 1.3 to 3.7 s to read a photo on the free server |
| Usability | The proposal planned SUS scores | `usability_test.md` | See that file |

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

## What testing changed

- A review reproduced three payment bugs: an abandoned MoMo Pay attempt blocked corrections forever, kept credit from being
  used, and a top-up after a correction looked like a double payment with no receipt. Each got a failing test, then a fix
  (`tests/services/test_unclaimed_payments.py`). Basic phones also gained a USSD step for the transaction ID.
- A meter added with no first reading billed the whole register. It is now held (`test_no_baseline.py`).
- Readings at 3 to 10 times normal use were billed because the check only ran inside the undeployed model. It is now a rule.
- Blur checking was turned off after calibration showed it fired more on readable photos.
