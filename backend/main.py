import os
import resource
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db, SessionLocal
from routes.reading import router as reading_router
from routes.billing import router as billing_router
from routes.ussd import router as ussd_router
from routes.anomaly import router as anomaly_router
from auth.routes import router as auth_router
from anomaly.config import AnomalyConfig
from anomaly.model import load_model_if_available
from ratelimit import upload_guard
from schemas import HealthResponse
from vision.models import registry as model_registry


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    model_registry.load()
    yield


app = FastAPI(
    title="WASAC Smart Water Billing Platform",
    description=(
        "AI-assisted water meter reading and billing for Kigali, Rwanda. "
        "Pipeline: YOLOv8 number-window crop → MobileNetV2 quality gate → "
        "ResNet18+BiGRU (CTC) digit reader → Isolation Forest anomaly detection."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

def _cors_origins() -> list:
    """CORS_ORIGINS: comma-separated origins, e.g. "https://wasac.vercel.app". Local dev by default."""
    raw = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
    return [origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip()]


# Added before CORS, so CORS wraps it (the last middleware added is the outermost): a refused
# upload never reaches the routes or has its body read, and its 413/429 still carries CORS
# headers, so the browser can read the message.
app.middleware("http")(upload_guard)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    # Optional, e.g. for Vercel preview URLs: ^https://wasac-[a-z0-9-]+\.vercel\.app$
    allow_origin_regex=os.getenv("CORS_ORIGIN_REGEX") or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(reading_router, tags=["Meter Reading"])
app.include_router(billing_router, tags=["Billing"])
app.include_router(ussd_router, tags=["USSD"])
app.include_router(anomaly_router, tags=["Anomaly Detection"])
app.include_router(auth_router, tags=["Staff sign-in"])


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
        quality_gate_model=model_registry.status["quality_gate"].label(),
        crnn_model=model_registry.status["reader"].label(),
        yolo_model=model_registry.status["yolo"].label(),
        photo_reading="ready" if model_registry.ready else "manual_entry_only",
        anomaly_detector=(
            "isolation_forest_loaded"
            if load_model_if_available(AnomalyConfig.from_env())
            else "rules_only_model_not_trained"
        ),
        memory_peak_mb=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024),  # Linux: KB
        timestamp=datetime.utcnow(),
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
