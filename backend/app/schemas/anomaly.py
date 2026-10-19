"""Anomaly scores, flags and the officers' review queue (app/api/routes/anomaly.py)."""
from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict


class AnomalyResultSchema(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    household_id: str
    reading_m3: Optional[float] = None
    daily_consumption: Optional[float] = None
    anomaly_score: Optional[float] = None
    is_anomaly: bool
    anomaly_type: str
    needs_retake: bool
    message_for_household: str
    features: dict = {}
    model_used: bool = False
    flag_id: Optional[int] = None
    pending_review: bool = False
    actions: List[str] = []


class AnomalyScoreRequest(BaseModel):
    household_id: str
    reading_digits: str
    reading_date: Optional[datetime] = None


class AnomalyFlagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    household_id: str
    reading_id: Optional[int] = None
    anomaly_type: str
    anomaly_score: Optional[float] = None
    features: Optional[dict] = None
    requires_staff_review: bool
    message_for_household: Optional[str] = None
    status: str
    created_at: datetime
    resolved_at: Optional[datetime] = None
    # The flagged reading's status: pending_review, valid (accepted), rejected, anomaly_flagged.
    # Lets the household see the outcome of a check ("confirmed" or "please read again").
    reading_status: Optional[str] = None


class ResolveFlagRequest(BaseModel):
    outcome: Optional[Literal["accept", "reject"]] = None


class ResolveFlagResponse(AnomalyFlagOut):
    outcome: Optional[str] = None
    reading_status: Optional[str] = None
    bill_id: Optional[int] = None
    amount_due: Optional[float] = None
    actions: List[str] = []


class HistoryPoint(BaseModel):
    date: datetime
    reading_m3: float
    consumption_m3: Optional[float] = None


class ReviewItem(BaseModel):
    flag: AnomalyFlagOut
    reading_m3: Optional[float] = None
    submitted_at: Optional[datetime] = None
    reading_confidence: Optional[float] = None
    customer_id: Optional[str] = None
    customer_name: Optional[str] = None
    sector: Optional[str] = None
    history: List[HistoryPoint] = []
