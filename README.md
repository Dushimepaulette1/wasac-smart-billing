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

```bash
cd wasac-platform/frontend
npm install
npm start
```

The app will be available at **http://localhost:3000**

---

## ML Model Performance

### CRNN Meter Reader

| Model | Exact Match Acc. | Integer Acc. | Mean Edit Distance |
|-------|-------------------|--------------|-------------------|
| EasyOCR (baseline) | 3.4% | 10.3% | 5.8 |
| CRNN (direct train) | 22.1% | 34.5% | 3.2 |
| CRNN (Yandex pretrain) | **38.0%** | **55.0%** | **2.15** |

### MobileNetV2 Quality Gate

| Dataset | Validation Accuracy |
|---------|---------------------|
| Yandex Toloka test set | 99.2% |
| Kigali field photos (n=13) | 33.3% |

> **Note:** The 33.3% accuracy on local Kigali photos reflects a documented domain gap between the European meter dataset (Yandex Toloka) and Rwandan field conditions (different lighting, meter brands, cover glass). Fine-tuning on WASAC-provided labeled data is planned for Phase 2.

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
│   ├── models/
│   │   ├── quality_gate.py  # Stage 1: MobileNetV2 stub
│   │   ├── crnn_model.py    # Stage 2: CRNN stub
│   │   └── anomaly_detector.py # Stage 3: Z-score / Isolation Forest
│   ├── routes/
│   │   ├── reading.py       # /submit-photo, /confirm-reading, /calculate-bill
│   │   ├── billing.py       # /customers, /bills
│   │   └── ussd.py          # /submit-ussd
│   └── requirements.txt
├── frontend/
│   ├── public/index.html
│   └── src/
│       ├── App.jsx          # Router
│       ├── App.css          # Design tokens & shared styles
│       ├── pages/
│       │   ├── CameraScreen.jsx
│       │   ├── ConfirmReading.jsx
│       │   ├── BillDisplay.jsx
│       │   ├── PaymentScreen.jsx
│       │   └── OfficerMode.jsx
│       └── components/
│           ├── BoundingBox.jsx
│           ├── QualityFeedback.jsx
│           └── TariffBreakdown.jsx
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
