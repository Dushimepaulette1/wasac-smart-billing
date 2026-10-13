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
│  POST /submit-ussd    GET  /health                              │
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
- Node.js 18+
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
MODEL_BASE_URL=<release download URL> python scripts/download_models.py

# 4. Create a .env file
cat > .env << 'ENVEOF'
DATABASE_URL=postgresql://wasac_user:wasac_pass@localhost:5432/wasac_db
AFRICASTALKING_API_KEY=your_sandbox_key_here
AFRICASTALKING_USERNAME=sandbox
ENVEOF

# 5. Create the PostgreSQL database
psql -U postgres -c "CREATE USER wasac_user WITH PASSWORD 'wasac_pass';"
psql -U postgres -c "CREATE DATABASE wasac_db OWNER wasac_user;"

# 6. Start the backend (auto-creates tables and seeds demo data)
python main.py
```

The API will be available at **http://localhost:8000**  
Swagger docs at **http://localhost:8000/docs**

### Frontend

React + TypeScript (strict), built with Vite.

```bash
cd wasac-platform/frontend
npm install
npm start          # dev server; backend routes are proxied to :8000
npm test           # Vitest + React Testing Library
npm run typecheck  # tsc --noEmit
npm run build      # type-check, then production build into build/
```

The app will be available at **http://localhost:3000**

Optional environment variables (in `frontend/.env`):

| Variable | Default | Meaning |
|---|---|---|
| `VITE_API_URL` | empty (use the dev proxy) | Backend base URL for a deployed build |
| `VITE_CUSTOMER_ID` | `CUST001` | Household shown until sign-in exists |
| `VITE_METER_ID` | `MTR001` | That household's meter |

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
| Loading, photo pipeline, guidance checks | `backend/vision/` |
| Every guidance threshold | `backend/vision/guidance_config.json` |

**Weights.** The `.pt` files (34 MB) are not in git. They are published as release assets, and
`scripts/download_models.py` fetches them from `MODEL_BASE_URL` into `backend/ml/` (or
`ML_WEIGHTS_DIR`) and checks each file's SHA-256 against `weights.sha256.json`. If a file is missing,
the API still starts: `/health` reports it, and `/submit-photo` answers with
`offer_manual_entry: true`, so the app asks the household to type the numbers.

**Held-out test results** (from `model_config.json`): 55.7% of readings exactly right on 79 photos
of 34 meters (95% CI 42–69%), and 70.9% within one digit. That is why every reading is shown to the
household to confirm, and why suspicious readings go to WASAC staff (see `backend/anomaly/README.md`).

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

Calibrate the thresholds on real photos with
`python scripts/calibrate_guidance.py --meters <folder> --non-meters <folder> --csv out.csv`. Measure
speed and memory with `python scripts/benchmark_vision.py [--photos <folder>]`.

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

## Deployment Plan

| Component | Platform | Notes |
|-----------|----------|-------|
| FastAPI backend | Render free tier (Docker) | Auto-deploy from `main` branch |
| React frontend | Render static site | Build: `npm run build` |
| PostgreSQL | Render managed database | Free tier (90-day retention) |
| SMS (Africa's Talking) | Sandbox during pilot | Switch to live on WASAC sign-off |
| MTN Mobile Money | Sandbox during pilot | Integration via REST sandbox API |

### Docker (backend)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## Project Structure

```
wasac-platform/
├── backend/
│   ├── main.py              # FastAPI app & lifespan
│   ├── database.py          # SQLAlchemy models & seed data
│   ├── schemas.py           # Pydantic request/response models
│   ├── ml/                  # model code + config shared with training; .pt weights downloaded
│   ├── vision/              # model loading, photo pipeline, guidance checks and thresholds
│   ├── anomaly/             # Stage 3: rules + Isolation Forest, pending review
│   ├── auth/                # staff sign-in
│   ├── routes/
│   │   ├── reading.py       # /submit-photo, /guide-frame, /confirm-reading, /calculate-bill
│   │   ├── billing.py       # /customers, /bills
│   │   ├── anomaly.py       # /api/anomaly/*
│   │   └── ussd.py          # /submit-ussd
│   ├── scripts/             # download_models, calibrate_guidance, benchmark_vision, anomaly tools
│   ├── tests/
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── vite.config.ts
│   └── src/
│       ├── api/             # Typed API client and FastAPI response models
│       ├── components/      # MeterCounter, Screen, Button, Notice, ...
│       ├── household/       # Household data loaders and submission state
│       ├── i18n/            # Kinyarwanda / English / French strings
│       ├── pages/           # One folder per screen
│       ├── router/          # Routes
│       └── styles/          # Design tokens, fonts, base typography
├── notebooks/
│   └── model_training.ipynb
└── README.md
```

---

## Demo Credentials

| Role | Username | Password |
|------|----------|----------|
| Field Officer | `officer` | `wasac2024` |

Demo customer: **CUST001** — Uwimana Jean Pierre, Kacyiru sector

---

## License

Academic capstone project — African Leadership University, 2024–2025.
