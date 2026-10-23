# WASAC Smart Water Billing Platform

A three-stage AI-assisted web platform for analog water meter reading and billing in Kigali, Rwanda. Combines **MobileNetV2** image quality classification, **CRNN** digit sequence recognition, and **Isolation Forest** anomaly detection with a React web interface and FastAPI backend.

**GitHub Repository:** PLACEHOLDER — to be added

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     React Frontend (Port 3000)                  │
│  CameraScreen → ConfirmReading → BillDisplay → PaymentScreen    │
│                     OfficerMode (field agent)                   │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP / REST
┌──────────────────────────▼──────────────────────────────────────┐
│                   FastAPI Backend (Port 8000)                   │
│  POST /submit-photo   POST /confirm-reading   POST /calculate-bill │
│  POST /ussd (USSD)    GET  /health   GET /health/ready          │
└──────┬───────────────────┬───────────────────┬──────────────────┘
       │                   │                   │
┌──────▼──────┐  ┌─────────▼──────┐  ┌────────▼────────┐
│  Stage 1    │  │   Stage 2      │  │   Stage 3       │
│ MobileNetV2 │  │  CRNN + CTC   │  │ Isolation Forest│
│ Quality Gate│  │ Digit Reader  │  │ Anomaly Detector│
└─────────────┘  └────────────────┘  └─────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│               PostgreSQL Database (Port 5432)                   │
│  customers · meters · readings · bills                          │
└──────────────────────────┬──────────────────────────────────────┘
                           │
              ┌────────────▼───────────┐
              │ Africa's Talking SMS   │
              │ (Sandbox Mode)         │
              └────────────────────────┘
```

---

## Setup & Installation

### Prerequisites
- Python 3.10+
- Node.js 20+ (Vitest 5)
- PostgreSQL 14+

### Backend

```bash
# 1. Clone the repository
git clone <REPO_URL>
cd wasac-platform/backend

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 3b. Download the model weights (not kept in git; see "Meter reading models" below)
MODEL_URLS="best.pt=<link>,meter_reader.pt=<link>,quality_gate.pt=<link>" python scripts/download_models.py

# 4. Create a .env file
cat > .env << 'ENVEOF'
DATABASE_URL=postgresql://wasac_user:wasac_pass@localhost:5432/wasac_db
AFRICASTALKING_API_KEY=your_sandbox_key_here
AFRICASTALKING_USERNAME=sandbox
ENVEOF

# 5. Create the PostgreSQL database
psql -U postgres -c "CREATE USER wasac_user WITH PASSWORD 'wasac_pass';"
psql -U postgres -c "CREATE DATABASE wasac_db OWNER wasac_user;"

# 6. Start the backend (auto-creates tables and seeds sample data)
uvicorn app.main:app --reload
```

The API will be available at **http://localhost:8000**  
Swagger docs at **http://localhost:8000/docs**

### Frontend

React + TypeScript (strict), built with Vite. One site: the household pages, and the staff area
under `/staff` (review queue, households, activity log, staff accounts). The staff pages are a
separate chunk, loaded only when `/staff` is opened; households see one small "WASAC staff? Sign in"
link at the foot of the start page.

```bash
cd wasac-platform/frontend
npm install
npm start          # http://localhost:3000 (staff: /staff); backend routes proxied to :8000
npm test           # Vitest + React Testing Library
npm run typecheck  # tsc --noEmit
npm run build      # type-check, then production build into build/
```

Optional environment variables (in `frontend/.env`):

| Variable | Default | Meaning |
|---|---|---|
| `VITE_API_URL` | empty (use the dev proxy) | Backend base URL for a deployed build |

---

## Meter reading models

`POST /submit-photo` runs: fix the phone's EXIF rotation → shrink the long side to 1,600 px →
**YOLOv8** finds the number window (`best.pt`) → photo guidance checks → **MobileNetV2** quality
gate on the crop (`quality_gate.pt`) → **ResNet18 + BiGRU (CTC)** reads the 8 wheels
(`meter_reader.pt`) → missing leading zeros are added. All three run on CPU and load once at start-up.

| What | Where |
|---|---|
| Model code shared with the training notebook | `backend/ml/wasac_models.py`, `backend/ml/wasac_preprocessing.py` |
| Input sizes, normalisation, quality-gate threshold, test results | `backend/ml/model_config.json` |
| Weight checksums | `backend/ml/weights.sha256.json` |
| Loading, photo pipeline, guidance checks | `backend/app/vision/` |
| Every guidance threshold | `backend/app/vision/guidance_config.json` |

**Weights.** The three `.pt` files (34 MB) are not in git and are not published anywhere public.
`scripts/download_models.py` downloads them into `backend/ml/` (or `ML_WEIGHTS_DIR`) and saves a
file only if its SHA-256 matches `backend/ml/weights.sha256.json`.

| Option | How |
|---|---|
| **Now: private Google Drive** | Share each file as "Anyone with the link", then set `MODEL_URLS="best.pt=<link>,meter_reader.pt=<link>,quality_gate.pt=<link>"`. Drive share links are converted to direct downloads. Keep the links in `backend/.env`, never in git. A plain folder link does not work, because each Drive file has its own id. |
| **Later: public release** | Only if Benax gives permission to redistribute `best.pt`. Attach the three files to a GitHub release and set `MODEL_BASE_URL=https://github.com/<owner>/<repo>/releases/download/<tag>`. |

If a file is missing, the API still starts: `/health` reports it, and `/submit-photo` answers with
`offer_manual_entry: true`, so the app asks the household to type the numbers.

**Usage limits on the weights:**
- `best.pt` belongs to Benax. Do not redistribute it without their permission.
- `meter_reader.pt` and `quality_gate.pt` are for **non-commercial academic use only**, because they
  were trained partly on the Yandex meter dataset (CC BY-NC-ND 4.0).

**Held-out test results** (from `model_config.json`): 55.7% of readings exactly right on 79 photos
of 34 meters (95% CI 42–69%), and 70.9% within one digit. That is why every reading is shown to the
household to confirm, and why suspicious readings go to WASAC staff (see `backend/app/anomaly/README.md`).

### Photo guidance

`/submit-photo` returns `guidance`, a list of codes with the most important first. **None of them
blocks a submission.**

| Code | Meaning |
|---|---|
| `NO_METER` | No number window was found. The reader is not run and no reading is suggested. |
| `TOO_FAR` | The number window is small in the frame |
| `CUT_OFF` | The window touches the edge of the photo |
| `TOO_DARK` / `GLARE` / `BLURRY` | Brightness, reflections and sharpness, measured on the crop |
| `HARD_TO_READ` | The quality gate scores the crop at or above its threshold |
| `CHECK_NUMBERS` | Low reader confidence, or a reading with more digits than the meter has |
| `OK` | None of the above |

`POST /guide-frame` takes a small camera frame (640 px max) for live framing hints. It runs YOLO plus
the brightness, glare and blur checks only, and returns the codes and the window's box in 0–1
coordinates.

The thresholds were calibrated on labelled WASAC photos; see
[docs/calibration/guidance_calibration.md](docs/calibration/guidance_calibration.md). To re-run the
calibration, use `scripts/calibrate_guidance.py measure`, then `... report` (see the script's help).
Calibration photos live in `calibration/`, which is gitignored and must never be committed. Measure
speed and memory with `python scripts/benchmark_vision.py [--photos <folder>]`.

> **OpenCV:** `ultralytics` installs `opencv-python` next to the `opencv-python-headless` we
> require. Both are version 4.11.0.86 and provide the same `cv2`, so nothing breaks, but a server
> install carries both packages. Left as is for now.

### Licences of third-party components

| Component | Licence | What it means here |
|---|---|---|
| Ultralytics / YOLOv8 (`ultralytics` package) | AGPL-3.0 | Offering the service over a network can oblige you to publish its source under the AGPL, unless you have an Ultralytics commercial licence |
| torchvision ImageNet pretrained weights (ResNet18, MobileNetV2 backbones) | BSD-3-Clause | Keep the copyright notice |
| Yandex water-meter dataset (used in training) | CC BY-NC-ND 4.0 | Models trained on it: non-commercial academic use only |
| `best.pt` (YOLOv8 window detector) | Benax, no redistribution licence granted | Ask Benax before sharing it |

---

## WASAC Tariff Tiers

| Tier | Usage | Rate (RWF/m³) |
|------|-------|---------------|
| Tier 1 | 0–5 m³ | 350 |
| Tier 2 | 6–15 m³ | 530 |
| Tier 3 | 16–30 m³ | 791 |
| Tier 4 | >30 m³ | 1,000 |
| Service charge | Fixed monthly | 1,000 |

---

## Deployment

| Part | Where | How |
|---|---|---|
| API (FastAPI) | Render free web service, Docker | `render.yaml` (Blueprint), `backend/Dockerfile` |
| App (React) | Vercel free | root directory `frontend`, `frontend/vercel.json` |
| Database | Neon free Postgres | `DATABASE_URL` |
| SMS | Africa's Talking sandbox | `AT_USERNAME=sandbox`, `AT_API_KEY` |
| Testing from this laptop | Cloudflare quick tunnel | `tools/phone_test.sh` |

**Models on ONNX Runtime.** The deployed API runs the three models with ONNX Runtime
(`backend/app/vision/onnx_models.py`) instead of PyTorch, so the image installs only
`requirements-serve.txt` and fits a 512 MB instance. `backend/scripts/export_onnx.py` makes the
`.onnx` files from the `.pt` ones and compares both: on 150 real meter photos plus 12 synthetic
ones they gave the same detections (boxes within 4 px), the same digits and the same retake
decisions. Locally, the API uses the `.onnx` files when they are present, else the `.pt` ones
(`VISION_BACKEND` forces either).

**Model files stay private.** Like the `.pt` files, the `.onnx` files (made from Benax's
`best.pt`) are never committed or put in the image. The container downloads them at start
(`MODEL_FORMAT=onnx`) from the links in the `MODEL_URLS` secret and checks their SHA-256 against
`backend/ml/weights.sha256.json`; logs show only file names.

**Settings on Render** (asked for when the Blueprint is created): `DATABASE_URL`, `MODEL_URLS`
(`best.onnx=<link>,meter_reader.onnx=<link>,quality_gate.onnx=<link>`), `CORS_ORIGINS` (the Vercel
address), `AT_USERNAME`, `AT_API_KEY`. `WASAC_AUTH_SECRET` is generated by Render.
**On Vercel:** `VITE_API_URL` = the Render address.

**Sleep.** A free Render service sleeps after 15 minutes without requests; the next request
waits for it to start again (about a minute: start, model download, model loading).

---

## Project Structure

```
wasac-platform/
├── backend/
│   ├── app/                     # the API (run: uvicorn app.main:app)
│   │   ├── main.py              # builds the app: start-up, guards (rate limits, CORS), routes
│   │   ├── api/
│   │   │   ├── deps.py          # who is asking? require_staff, require_role, household_access
│   │   │   └── routes/          # one file per area:
│   │   │       ├── readings.py        # /submit-photo, /guide-frame, /confirm-reading, /calculate-bill
│   │   │       ├── billing.py         # /customers, /customers/{id}/bills, /bills/{id}/pay
│   │   │       ├── anomaly.py         # /api/anomaly/* (messages, review queue, decisions)
│   │   │       ├── household_auth.py  # /household/* (SMS sign-in)
│   │   │       ├── staff_auth.py      # /auth/* (staff sign-in, activity, accounts)
│   │   │       ├── ussd.py            # /ussd (Africa's Talking USSD menu)
│   │   │       └── health.py          # /health
│   │   ├── core/                # config.py (settings), security.py (passwords, tokens), ratelimit.py
│   │   ├── db/                  # session.py (connection), init_db.py (tables), seed.py (local samples)
│   │   ├── models/              # database tables (from app.models import Customer, Bill, ...)
│   │   ├── schemas/             # request/response shapes (from app.schemas import ...)
│   │   ├── services/            # billing.py (tariff), sms.py (Africa's Talking), audit.py (staff log)
│   │   ├── anomaly/             # leaks and wrong readings: rules + Isolation Forest, location check, review
│   │   ├── vision/              # meter-photo models (PyTorch or ONNX), pipeline, live guidance
│   │   └── utils/               # small helpers (phone numbers)
│   ├── ml/                      # model code + config shared with the training notebook; weights downloaded here
│   ├── scripts/                 # download_models, export_onnx, create_officer, demo data, calibration, training
│   ├── tests/                   # pytest, mirroring app/ (api/, anomaly/, core/, ...); helpers in tests/support/
│   ├── requirements.txt         # full environment (training, .pt models, tests)
│   ├── requirements-serve.txt   # what the deployed API needs (ONNX, no torch)
│   ├── Dockerfile, start.sh     # the container Render runs
│   └── README.md
├── frontend/
│   ├── index.html
│   ├── vite.config.ts
│   ├── tests/                   # Vitest, mirroring src/ (api/, components/, pages/, ...); helpers in tests/support/
│   └── src/
│       ├── api/             # Typed API client and FastAPI response models
│       ├── components/      # MeterCounter, Screen, Button, Notice, ...
│       ├── household/       # Household data loaders and submission state
│       ├── i18n/            # Kinyarwanda (default) / English strings
│       ├── pages/           # One folder per screen
│       ├── router/          # HouseholdRoutes, and StaffRoutes under /staff
│       └── styles/          # Design tokens, fonts, base typography
├── notebooks/
│   └── wasac_meter_reading_pipeline.ipynb
└── README.md
```

### Paying with MTN Mobile Money

`POST /bills/{id}/pay` starts a payment (`backend/app/services/payments.py`). With MoMo keys it uses
MTN's Collections **Request to Pay**: MTN sends a PIN prompt to the household's phone, the app
waits ("Approve the payment on your phone") and checks `GET /payments/{id}` every 3 s; on success
the bill is marked paid once and an SMS receipt is sent; a declined payment takes nothing and can
be tried again; a pending attempt is reused, never sent twice. Without keys, payments are
simulated and the receipt says "Test payment".

Sandbox setup: sign up at momodeveloper.mtn.com, subscribe to **Collections**, put its primary
key in `backend/.env` as `MOMO_SUBSCRIPTION_KEY`, run `python scripts/momo_sandbox_setup.py` (it
creates the API user and key and adds them to `.env`), then copy the three `MOMO_` values to
Render. The sandbox uses test money in EUR and approves by itself.

### USSD for basic phones

`POST /ussd` is the Africa's Talking USSD callback (`backend/app/services/ussd_menu.py`):
Kinyarwanda first (9 for English), 1 send a reading (8 digits, then confirm), 2 my bill, 3 pay
my bill (MoMo prompt). The same rules apply as in the app. The callback URL must carry the
secret `?token=<USSD_CALLBACK_TOKEN>` (Render generates it); without it the endpoint refuses, so
nobody can act for someone else's number. In the Africa's Talking sandbox: USSD → create a
channel → callback `https://wasac-api.onrender.com/ussd?token=<the token>`.

### Installable app (PWA)

The household app can be installed on a phone's home screen and opens like an app (no browser
bar), even on a weak or missing connection:

- `frontend/public/manifest.webmanifest`: name, Kinyarwanda first, icons, home-screen shortcuts
  (read the meter, bills, messages).
- `frontend/public/sw.js`, the service worker: the app shell opens from the phone after 4 s
  without network (or offline); built files are cached by their unique names; **API data (bills,
  readings, sign-in) is never cached**. Registered in production builds only
  (`src/pwa/registerServiceWorker.ts`).
- "Install the app": a button on Android (`beforeinstallprompt`), a Share → Add to Home Screen
  hint on iPhone, hidden once installed (`src/pwa/`).
- Icons: a meter counter on the night stage, drawn in `frontend/icons/*.svg` and rendered to
  `frontend/public/` (192, 512, maskable 512, Apple 180, favicons).

### Tests

Both sides keep tests apart from the code, in a `tests/` folder that mirrors the code's folders,
and name each test as a sentence: **when** this happens, it **should** do that.

| | Run | Layout | Name |
|---|---|---|---|
| Backend | `cd backend && pytest` | `tests/api/test_household_auth.py` tests `app/api/routes/household_auth.py` | `test_when_a_household_asks_for_another_account_should_return_404` |
| Frontend | `cd frontend && npm test` | `tests/pages/SignIn.test.tsx` tests `src/pages/SignIn/SignIn.tsx` | `it('when the code is wrong, should say so')` |

GitHub Actions runs both on every push and pull request (`.github/workflows/ci.yml`), with no
secrets: the backend tests use an in-memory database and fake models and can never reach Neon,
Africa's Talking or MTN (`backend/tests/conftest.py`).

**Health:** `GET /health` is Render's check and stays 200 while the process answers; it reports
`degraded` if the database cannot be reached. `GET /health/ready` answers 503 in that case: point
an uptime monitor at it.

---

## Staff accounts

There are no built-in staff passwords. Create the first admin with the script (it asks for the
password twice and never prints it); that admin then adds everyone else under **Staff accounts**
in the staff area, where each new or reset account gets a one-time temporary password.
Someone signed in with a temporary password can only open **My account** until they choose their
own. Changing or resetting a password ends every session signed in with the old one (staff tokens
carry a stamp of the password, `backend/app/core/security.py`).

```bash
cd backend
python scripts/create_officer.py <username> --name "Full Name" --role admin
# Forgotten password: run it again for the same username to set a new one.
```

| Role | Can |
|---|---|
| `officer` | Review held readings, see households, see their own activity |
| `supervisor` | As officer, plus everyone's activity |
| `admin` | As supervisor, plus add accounts, change roles, turn accounts off, reset passwords |

Every sign-in (and failed attempt), review decision and account change is recorded in the
`staff_actions` table and shown under **Activity**.

## Household sign-in and the location check

Households sign in with the phone number on their WASAC account and a 6-digit code sent by SMS
(no password). The session lasts 30 days on that phone. A household sees only the accounts on
its own number; staff see all. Codes are stored only as a keyed hash, work once, for 10 minutes
and 5 tries; requests are limited per number and per IP. A number that is not on any account is
told so plainly (call WASAC on 1580), so nobody waits for a code that will never come; the per-IP
limit keeps anyone from checking numbers in bulk.

When a household confirms a reading, the app sends where the phone was when the photo was taken
and whether it came from the camera or the gallery. Compared with the meter's location on file
(`backend/app/anomaly/location.py`), a photo more than 150 m away (allowing for the phone's
accuracy), with no location, with a very rough location, or chosen from the gallery is **held
for an officer** (type `LOCATION_CHECK`), who sees why in the review queue and can accept it.
Readings are never rejected for this alone; location can be faked, so it decides who gets a
second look, nothing more. A meter with **no location on file** has its first located photo
checked by an officer once; accepting it saves where the photo was taken (if the phone was
accurate to 100 m) as the meter's location, and later readings are checked against it.

**One reading per period, one at a time** (`backend/app/services/reading_window.py`): while a
reading waits for an officer, the household cannot send another; after a reading is accepted, the
next one opens 25 days later. The app says why and when; staff can always enter a reading.
Each reading is saved with its meter locked, so two at once (a double tap, a retry, the app and
USSD together) are taken one after the other; the same value again within 2 minutes is refused,
and the database allows only one bill per reading.

**Review queue.** A held reading is accepted (billed) or rejected (the household reads again). A
reading that was billed but needs a look (meter seems stuck, high use for months) is **closed**
once followed up. Officers see the meter photo the reading came from, what the photo reader read,
and whether the household changed it (`backend/app/services/photo_evidence.py`). Photos are kept
`PHOTO_RETENTION_DAYS`, then deleted; a photo never confirmed is deleted after a day.

| Setting (`backend/.env`) | Default | Meaning |
|---|---|---|
| `WASAC_AUTH_SECRET` | random at start-up | Signs sessions and code hashes; set it, or everyone is signed out on restart |
| `OTP_SHOW_DEMO_CODES` | `1` | Show sign-in codes on screen for DEMO- households (SMS not wired yet) |
| `LOCATION_MAX_M` | `150` | How far from the meter a photo may be taken |
| `LOCATION_MAX_ACCURACY_M` | `500` | Rougher phone positions count as "unclear" |
| `AT_USERNAME`, `AT_API_KEY` | unset (SMS only logged) | Africa's Talking; `sandbox` sends to the simulator only |
| `AT_SENDER_ID` | unset | Approved sender name (live only) |
| `SMS_OUTBOX` | `1` | Keep sandbox SMS for admins to read under **Sent SMS** (the sandbox reaches no real phone) |
| `MIN_DAYS_BETWEEN_READINGS` | `25` | Days between accepted readings (`0` turns the rule off, e.g. for testing) |
| `LOCATION_SAVE_MAX_ACCURACY_M` | `100` | How precise a first photo must be to become the meter's location |
| `MOMO_SUBSCRIPTION_KEY`, `MOMO_API_USER`, `MOMO_API_KEY` | unset (simulated payments) | MTN MoMo Collections |
| `USSD_CALLBACK_TOKEN` | unset (USSD off) | Secret in the Africa's Talking USSD callback URL |
| `PHOTO_RETENTION_DAYS` | `90` | How long meter photos are kept for reviewers |

**Demo households** (`scripts/demo/generate_demo_households.py --load-db`, all `DEMO-`, labelled
"Demo data" in the app): sign in with **0700 000 001** for DEMO-MTR-001, 0700 000 002 for
DEMO-MTR-002, and so on to 0700 000 018; **0700 000 019** has two meters (019 and 020), to show
choosing a meter. These are not real numbers; the code is shown on screen. To try SMS sign-in
with your own phone: `--set-phone DEMO-MTR-001 07XXXXXXXX` (and `--update-contacts` to undo). DEMO-MTR-002 has a
location on file (Kacyiru), so its readings show the location check. `--update-contacts` sets the
phones and location on DEMO- rows already in the database.

---

## License

Academic capstone project — African Leadership University, 2024–2025.
