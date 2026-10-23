"""Is the server well? The app never needs these.

    GET /health        liveness, for Render's health check: 200 while the process answers;
                       status "degraded" (still 200) if the database cannot be reached, so a
                       database that is waking up (Neon) does not get a good deploy restarted
    GET /health/ready  readiness, for an uptime monitor: 503 unless the database answers
"""
import resource
from datetime import datetime

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.anomaly.config import AnomalyConfig
from app.anomaly.model import load_model_if_available
from app.db.session import SessionLocal
from app.schemas import HealthResponse
from app.vision.models import registry as model_registry

router = APIRouter()


def _database_status() -> str:
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        return "connected"
    except Exception:
        return "disconnected"


# Plain def, not async: the database call blocks, so FastAPI runs these in a worker thread.
@router.get("/health", response_model=HealthResponse)
def health_check():
    db_status = _database_status()
    return HealthResponse(
        status="ok" if db_status == "connected" else "degraded",
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


@router.get("/health/ready")
def readiness():
    db_status = _database_status()
    return JSONResponse({"status": "ok" if db_status == "connected" else "unavailable", "database": db_status},
                        status_code=200 if db_status == "connected" else 503)
