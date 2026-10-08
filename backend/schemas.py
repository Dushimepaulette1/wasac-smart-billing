from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import datetime


class PhotoSubmitResponse(BaseModel):
    status: str  # "readable" | "unreadable"
    predicted_reading: Optional[str] = None
    confidence: Optional[float] = None
    quality_gate_score: Optional[float] = None
    guidance_message: Optional[str] = None


class ConfirmReadingRequest(BaseModel):
    customer_id: str
    meter_id: str
    confirmed_reading: str


class TariffBreakdown(BaseModel):
    tier1_units: float
    tier1_rate: int = 350
    tier1_amount: float
    tier2_units: float
    tier2_rate: int = 530
    tier2_amount: float
    tier3_units: float
    tier3_rate: int = 791
    tier3_amount: float
    tier4_units: float
    tier4_rate: int = 1000
    tier4_amount: float
    service_charge: float = 1000.0
    total: float


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


class ConfirmReadingResponse(BaseModel):
    success: bool
    bill_amount: Optional[float] = None
    consumption_m3: Optional[float] = None
    tariff_breakdown: Optional[TariffBreakdown] = None
    validation_status: str
    anomaly_flagged: bool = False
    anomaly_score: Optional[float] = None
    error_message: Optional[str] = None
    bill_id: Optional[int] = None
    anomaly: Optional[AnomalyResultSchema] = None


class BillCalculateRequest(BaseModel):
    consumption_m3: float


class USSDRequest(BaseModel):
    phone_number: str
    reading_value: str
    session_id: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    database: str
    quality_gate_model: str
    crnn_model: str
    anomaly_detector: str
    timestamp: datetime


class CustomerInfo(BaseModel):
    customer_id: str
    name: str
    phone: str
    sector: str
    meter_id: str
    last_reading: float
    last_reading_date: Optional[datetime]
    avg_consumption: Optional[float]
    anomaly_flagged: bool = False

    class Config:
        from_attributes = True
