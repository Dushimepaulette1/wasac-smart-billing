"""Photo reading, live tips and confirming a reading (app/api/routes/readings.py)."""
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from app.schemas.anomaly import AnomalyResultSchema
from app.schemas.billing import TariffBreakdown


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
    # Send back with /confirm-reading: the officer who checks the reading then sees this photo.
    photo_id: Optional[str] = None


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


class GeoPoint(BaseModel):
    lat: float = Field(ge=-90, le=90, allow_inf_nan=False)
    lng: float = Field(ge=-180, le=180, allow_inf_nan=False)
    accuracy_m: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)


class ConfirmReadingRequest(BaseModel):
    customer_id: str
    meter_id: str
    confirmed_reading: str
    # Where the phone was when the photo was taken; None if the household refused or there was no fix.
    location: Optional[GeoPoint] = None
    # "upload": chosen from the gallery, so it may be old or from elsewhere.
    photo_source: Literal["camera", "upload"] = "camera"
    # From /submit-photo; None when the numbers were typed without a photo.
    photo_id: Optional[str] = Field(default=None, max_length=32)


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
