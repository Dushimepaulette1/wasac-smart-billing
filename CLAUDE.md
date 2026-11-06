# CLAUDE.md

Mubazi ("water meter" in Kinyarwanda): a household photographs its water meter, AI reads the digits,
the household confirms them, rules check the reading, and it is billed or held for a WASAC officer.
It is a capstone prototype by Dushime Paulette (African Leadership University), not an official WASAC
service. All households are made up.

The principle behind every feature: **the AI helps, people decide.** The reader gets 55.7% of meters
fully right on unseen photos (95% CI 42 to 69%), so a person always confirms the digits.

## Commands

Python 3.10 and Node 22 (CI and Docker use these; jsdom needs Node 22.10+).

```bash
# Backend (from backend/)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt     # requirements.txt alone has no pytest
cp .env.example .env                    # for a quick start set DATABASE_URL=sqlite:///./local.db
python scripts/demo/generate_demo_households.py --load-db
python scripts/create_officer.py admin --name "Your Name" --role admin
uvicorn app.main:app --reload           # :8000, API docs at /docs

pytest                                  # all tests
pytest tests/services/test_payments.py -k "mtn"   # one file or name
pytest --cov=app --cov-report=term      # coverage, as CI runs it

# Frontend (from frontend/)
npm install
npm start                               # :3000, proxies the API to :8000; staff area at /staff
npx vitest run                          # all tests once (npm test stays in watch mode)
npx vitest run tests/pages/SignIn.test.tsx
npm run typecheck
npm run build                           # tsc, then vite build into build/
npm run i18n:sync                       # after changing en.json
```

PostgreSQL race tests are skipped unless `TEST_POSTGRES_URL` is set. The database name must contain
"test", because every test wipes it:

```bash
docker run -d --rm --name mubazi-pg-test -p 5433:5432 -e POSTGRES_PASSWORD=test -e POSTGRES_DB=mubazi_test postgres:16
TEST_POSTGRES_URL=postgresql://postgres:test@localhost:5433/mubazi_test pytest -m postgres
```

CI (`.github/workflows/ci.yml`) runs backend tests with Postgres, frontend typecheck, tests and build,
and a Chromium, Firefox and WebKit check of the production build (`tools/e2e/compat_check.mjs`).
There is no linter or formatter configured on either side.

Run `tools/e2e/live_e2e.mjs` against localhost unless told otherwise: it changes data. It refuses
other hosts without `E2E_ALLOW_LIVE=1`.

## Layout

| Path | What |
|---|---|
| `backend/app/api/routes/` | One file per area. Thin: auth, parse, call a service |
| `backend/app/api/deps.py` | Who is asking: `require_staff`, `require_role`, `household_access`, `meter_for` |
| `backend/app/services/` | Billing, payments, balance, corrections, SMS, push, USSD menu |
| `backend/app/anomaly/` | Reading checks. `evaluation.py` is every check (read-only), `service.py` stores, `review.py` is officer decisions. Has its own README |
| `backend/app/vision/` | Photo pipeline and guidance checks, on ONNX or PyTorch |
| `backend/app/models/`, `schemas/` | SQLAlchemy tables, Pydantic API models |
| `backend/ml/` | Model code shared with the training notebook, config, weight checksums |
| `backend/simulation/` | Offline anomaly simulation. Nothing in the app uses it |
| `backend/scripts/` | Admin, demo data, training, calibration, ONNX export |
| `frontend/src/api/` | `client.ts` is the only place that calls the backend; `types.ts` mirrors the schemas; `useRequest.ts` gives loading, failed and retry states |
| `frontend/src/pages/`, `components/` | Each in its own folder with a `.module.css`; staff pages are in `pages/staff/` |
| `frontend/src/household/`, `staff/` | Session, loaders and logic for each audience |
| `frontend/src/router/` | Household routes, plus `/staff` as a lazy chunk so households never download it |
| `docs/` | `TECHNICAL_GUIDE.md`, `ALGORITHMS.md`, `decisions/OPEN_ITEMS.md`, `testing/README.md`, report. The PDF is built from `report/technical_report.html` and must stay at 5 pages or fewer |

## How a reading flows

1. `POST /submit-photo`: YOLOv8 finds the number window, MobileNetV2 scores quality, ResNet18 + BiGRU
   (CTC) reads 8 wheels. Guidance codes never block a submission. With no model files the app still
   works: the response has `offer_manual_entry: true` and the household types the digits.
2. `POST /check-reading` runs the checks and stores nothing. `POST /confirm-reading` runs the same
   `evaluate_reading` again with the meter row locked.
3. The result is billed (`valid`, or `anomaly_flagged` for a follow-up) or held (`pending_review`).
4. An officer resolves a held reading with `PATCH /api/anomaly/flags/{id}/resolve`.

8 wheels: the first 5 are m³ and the last 3 are litres, so `00565846` is 565.846 m³. A meter wraps at
99,999. In the anomaly code a "household" means a meter: `household_id` is `meter_id`.

## Rules that must hold

Billing and money:
- Never change a reading, bill or payment that has happened. Corrections add adjustments
  (`services/bill_corrections.py`).
- `services/balance.py` is the only definition of what is owed. `bills.payment_status` only says a
  payment arrived. Do not compute "unpaid" anywhere else.
- Never edit a tariff version that bills use. Add a new entry to `services/tariffs.json`; each bill
  keeps its own version. Rates are provisional.
- Only MTN's success or failure status closes a payment by itself. A timeout, 5xx or 404 stays
  pending, and nothing may send a second prompt.
- One open attempt per bill, one bill per reading: keep the row locks, partial unique indexes and
  idempotency keys. SQLite cannot show these races, so concurrency work needs `tests/pg/`.
- A correction that charges more needs a second person, and starting-reading changes do too (unless
  the meter has no starting value). The requester cannot approve their own.

Readings:
- Readings are held for a person, never rejected automatically. Location is only a reason for a
  second look, because it can be faked.
- A `pending_review` reading is not billed, does not move `meters.last_reading` and is not history.
- A first reading with no baseline creates no bill. It is held, and accepting it sets the start.
- Production is rules only. The Isolation Forest has never seen real data and must not be deployed
  or reported as if it had. Thresholds are provisional (`app/anomaly/README.md`).

Security and access:
- Check access server-side. A household asking for another account gets 404, not 403 (`meter_for`).
- Record staff actions with `services/audit.py`.
- Household API data is never cached by the service worker.
- `/ussd` stays refused without `USSD_CALLBACK_TOKEN`.
- Never log phone numbers unmasked, sign-in codes, keys or `MODEL_URLS`. `backend/start.sh` must not
  use `set -x` or print the environment.

Honest reporting: this is a graded project. Keep real, simulated and synthetic results labelled as
such. Never present simulation numbers (forest F1 0.89) as real performance, and do not guess a WASAC,
RURA or MTN policy into the code: add it to `docs/decisions/OPEN_ITEMS.md`.

## Never commit

`.env`, `*.pt`, `*.onnx` and other weights, `calibration/` (real household photos), `*.local.txt`
(staff passwords). `best.pt` belongs to Benax and must not be redistributed. The other two models are
non-commercial academic use only (Yandex dataset, CC BY-NC-ND 4.0). Do not add them to the Docker image.

## Making changes

**New database column or index.** Add a reviewed Alembic revision under `backend/migrations/versions/`
and update the model. Startup applies revisions and stops on migration failure. Test new and existing
databases on PostgreSQL and SQLite. `LATE_COLUMNS` and `LATE_INDEXES` remain only as legacy helpers.

**New backend path.** Add it to `API_PATHS` in `frontend/vite.config.ts` and in
`frontend/public/sw.js` (unless it sits under an existing prefix), and add its route file to the
docstring in `app/api/__init__.py`. Update `frontend/src/api/types.ts` when a response changes.

**New setting.** Read it from the environment where it is used, so tests can change it, and add it
to `backend/.env.example`. If it is needed live, add it to `render.yaml` and the table in the
technical guide.

**New user-facing text.** Everything goes through `t()` from `useI18n()`, with a flat key in
`frontend/src/i18n/locales/en.json`, then `npm run i18n:sync`. Kinyarwanda is the default language.
Never machine-translate it: new strings stay `TODO: translate` and fall back to English. Run
`npm run i18n:review -- new <name> <keys>` to make a sheet for a human reviewer. Allow for strings
up to 50% longer than English.

**Dependencies.** The API serves from `requirements-serve.txt` on 512 MB of memory with no torch.
A new runtime dependency goes in both `requirements-serve.txt` and `requirements.txt`, and heavy ones
need a good reason. The frontend has only React and react-router at runtime. Keep it that way.

## Conventions

- Tests live in `tests/`, mirroring the code's folders, and read as sentences:
  `test_when_a_household_asks_for_another_account_should_return_404`,
  `it('when the code is wrong, should say so')`. Shared helpers are in `tests/support/`.
- Backend tests use in-memory SQLite and fake models. `conftest.py` blocks real SMS, Neon and model
  files, so keep tests behind those fixtures: `client` (officer), `as_admin`, `household_client`,
  `anon_client`, `photo_client`.
- Each file starts with a docstring (`@file` and `@description` in the frontend) saying what it is
  for. Comments explain why, in plain words. Split a file before it grows large.
- Staff copy and errors are plain sentences that say how to fix the problem ("Reading lower than last
  month", not `MISREAD_SUSPECTED`). Held readings never accuse the household.
- TypeScript is strict, with no unused locals or parameters. Use CSS Modules and the role tokens in
  `src/styles/tokens.css`.

Frontend design:
- The household app is mobile first at 360px on cheap Android phones, often outdoors on weak data:
  tap targets of 48px or more, no horizontal scroll, every network action has loading, failed and
  retry states, and photos and typed digits survive a failure.
- The meter counter (`components/MeterCounter`) is the signature element: black cells for m³, red for
  litres. Red is used nowhere else, including errors. Use it only for readings, never for money.
- Money is "RWF 4,500", dates are DD/MM/YYYY. No droplet or wave imagery, no animation libraries.
- Build targets include chrome80 and safari14.

## Project rules and stale documents

- Do not add AI attribution to anything in this repository: no `Co-Authored-By` lines in commits, and no generated-by lines in pull requests.
- `.claude/skills/wasac-frontend-design/SKILL.md` keeps its useful constraints but predates the
  current design. It says react-i18next, French and a dark gradient. The app uses its own
  `I18nProvider`, Kinyarwanda and English only, and "Navy and Ink" (Instrument Serif and Josefin
  Sans, light by default, dark as "night"). See `tokens.css` and the last section of
  `docs/design/DESIGN_PLAN.md`.
- The polling and single-worker settings in `vite.config.ts` were added for WSL.
- README and report test totals come from the dated run linked in `docs/testing/README.md`. If tests
  are added, update the figures from a real run, not by estimate; keep local and CI evidence separate.

## Deployment and status

API on Render (Docker, free plan, `render.yaml`, `autoDeploy: true`), frontend on Vercel, database
on Neon Postgres. Free Render sleeps after 15 minutes, so the first request takes about a minute.
Deployed models are ONNX, downloaded at container start. Secrets are never in the repo.

Live: https://wasac-smart-billing-qt9t.vercel.app. Treat pushing to main as deploying to
the live site. Demo households are 0700 000 021 to 026 and 031 to 039 live (039 has two meters), and `0700 000 0NN` for KGL-200NN locally; the
sign-in code appears on screen.

Simulated today: SMS (sandbox), payments (no real money), USSD (no live channel), demo households.
The walkthrough video is linked in `README.md`; access and technical content still need author review.
See `docs/decisions/OPEN_ITEMS.md`. Working notes were deliberately removed from the repo, so do
not add video scripts, checklists or review notes back.
