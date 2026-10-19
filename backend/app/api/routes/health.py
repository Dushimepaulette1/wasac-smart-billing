"""GET /health: is the server well? Render calls it every few seconds; the app never needs it."""
import resource
from datetime import datetime

from fastapi import APIRouter
from sqlalchemy import text

from app.anomaly.config import AnomalyConfig
from app.anomaly.model import load_model_if_available
from app.db.session import SessionLocal
from app.schemas import HealthResponse
from app.vision.models import registry as model_registry

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    db_status = "connected"
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
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
