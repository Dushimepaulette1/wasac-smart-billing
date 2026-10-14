from pydantic import BaseModel, ConfigDict
from typing import Dict, List, Literal, Optional
from datetime import datetime


class PhotoSubmitResponse(BaseModel):
    # Fields the current app reads. "unreadable" means: no reading suggested, offer manual entry.
    status: str  # "readable" | "unreadable"
    predicted_reading: Optional[str] = None   # = raw_digits
    confidence: Optional[float] = None        # = confidence_min
    quality_gate_score: Optional[float] = None
    guidance_message: Optional[str] = None    # unused; guidance codes are translated by the app

    models_ready: bool = False
    offer_manual_entry: bool = True
    guidance: List[str] = []                  # most important first; never blocks a submission
    raw_digits: Optional[str] = None
    reading_digits: Optional[str] = None      # 8 digits, or null when the read is impossible
    reading_m3: Optional[float] = None
    confidence_min: Optional[float] = None
    confidence_mean: Optional[float] = None
    needs_check: bool = False
    quality_score: Optional[float] = None     # P(unreadable) from the quality gate
    crop_method: str = "none"
    thumbnail_jpeg_base64: Optional[str] = None
    timings_ms: Dict[str, float] = {}


class NormalizedBox(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float


class GuideFrameResponse(BaseModel):
    available: bool                           # false when the window detector is not loaded
    guidance: List[str]
    box: Optional[NormalizedBox] = None       # number window, 0-1 coordinates
    box_method: str = "none"
    elapsed_ms: float


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
    yolo_model: str
    photo_reading: str                        # "ready" or "manual_entry_only"
    anomaly_detector: str
    memory_peak_mb: Optional[int] = None      # peak resident memory of the API process
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


class LoginRequest(BaseModel):
    username: str
    password: str


class StaffUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    username: str
    full_name: str
    role: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: int
    user: StaffUserOut


class StaffActionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    at: datetime
    username: str
    action: str
    target: Optional[str] = None
    detail: Optional[str] = None


class StaffAccountOut(StaffUserOut):
    is_active: bool
    created_at: datetime
    last_sign_in: Optional[datetime] = None


class StaffAccountCreate(BaseModel):
    username: str
    full_name: str
    role: Literal["officer", "supervisor", "admin"] = "officer"


class StaffAccountUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[Literal["officer", "supervisor", "admin"]] = None
    is_active: Optional[bool] = None


class TemporaryPasswordResponse(BaseModel):
    """The new account's (or reset) password, shown once to the admin to pass on."""
    account: StaffAccountOut
    temporary_password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


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
