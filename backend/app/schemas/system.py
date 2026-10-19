"""The health check and the USSD menu (app/api/routes/health.py, ussd.py)."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    database: str
    quality_gate_model: str
    crnn_model: str
    yolo_model: str
    photo_reading: str                        # "ready" or "manual_entry_only"
    anomaly_detector: str
    memory_peak_mb: Optional[int] = None      # peak resident memory of the API process
    timestamp: datetime


class USSDRequest(BaseModel):
    phone_number: str
    reading_value: str
    session_id: Optional[str] = None
