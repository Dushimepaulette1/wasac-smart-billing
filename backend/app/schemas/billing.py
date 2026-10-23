"""Bills, the tariff breakdown and household details (app/api/routes/billing.py)."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


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


class BillCalculateRequest(BaseModel):
    consumption_m3: float


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
    # Can the household send a reading now? (app/services/reading_window.py)
    reading_pending: bool = False                 # one is waiting for an officer
    next_reading_from: Optional[datetime] = None  # this period's reading is in; the next opens then
    # Bills not paid yet, for the staff overview (one request instead of one per household).
    unpaid_count: int = 0
    unpaid_amount: float = 0.0

    class Config:
        from_attributes = True


class MeterCorrectionRequest(BaseModel):
    """Staff set a meter's current reading (a replaced meter, or a wrong record)."""
    reading_m3: float = Field(ge=0, le=99_999.999)
    reason: str = Field(min_length=3, max_length=200)


class PaymentOut(BaseModel):
    """One attempt to pay a bill. status: pending (waiting for the payer's PIN), successful, failed."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    bill_id: int
    provider: str                 # momo, momo_sandbox, simulated
    status: str
    amount: float
    currency: str
    transaction_id: Optional[str] = None
    reason: Optional[str] = None
    already_paid: bool = False
