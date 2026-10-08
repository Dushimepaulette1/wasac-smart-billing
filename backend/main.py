import os
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db, SessionLocal
from routes.reading import router as reading_router
from routes.billing import router as billing_router
from routes.ussd import router as ussd_router
from routes.anomaly import router as anomaly_router
from anomaly.config import AnomalyConfig
from anomaly.model import load_model_if_available
from schemas import HealthResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="WASAC Smart Water Billing Platform",
    description=(
        "AI-assisted water meter reading and billing for Kigali, Rwanda. "
        "Three-stage pipeline: MobileNetV2 quality gate → CRNN digit reader → "
        "Isolation Forest anomaly detection."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(reading_router, tags=["Meter Reading"])
app.include_router(billing_router, tags=["Billing"])
app.include_router(ussd_router, tags=["USSD"])
app.include_router(anomaly_router, tags=["Anomaly Detection"])


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    db_status = "connected"
    try:
        db = SessionLocal()
        db.execute(__import__("sqlalchemy").text("SELECT 1"))
        db.close()
    except Exception:
        db_status = "disconnected"

    return HealthResponse(
        status="ok",
        database=db_status,
        quality_gate_model="stub_active",
        crnn_model="stub_active",
        anomaly_detector=(
            "isolation_forest_loaded"
            if load_model_if_available(AnomalyConfig.from_env())
            else "rules_only_model_not_trained"
        ),
        timestamp=datetime.utcnow(),
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
