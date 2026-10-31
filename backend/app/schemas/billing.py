"""Bills, the tariff breakdown and household details (app/api/routes/billing.py)."""
from datetime import datetime
from typing import Literal, List, Optional

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
    consumption_m3: float = Field(ge=0, le=99_999.999, allow_inf_nan=False)
    tariff_version: Optional[str] = Field(default=None, max_length=40)  # an old bill's rates; none: today's


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
    unpaid_amount: float = 0.0     # what is actually owed, after payments, credit and corrections
    credit_available: float = 0.0  # kept for the next bills; there are no cash refunds in the app
    serial_number: Optional[str] = None
    is_demo: bool = False                         # a DEMO- test household

    class Config:
        from_attributes = True


class HouseholdIn(BaseModel):
    """Staff add a household (app/services/households.py checks and cleans every field)."""
    name: str = Field(max_length=200)
    phone: str = Field(max_length=40)
    meter_id: str = Field(max_length=60)
    sector: str = Field(max_length=100)
    serial_number: Optional[str] = Field(default=None, max_length=60)
    first_reading: Optional[str] = Field(default=None, max_length=20)
    customer_id: Optional[str] = Field(default=None, max_length=60)


class HouseholdEdit(BaseModel):
    """Staff change a household's details. The meter number does not change."""
    name: str = Field(max_length=200)
    phone: str = Field(max_length=40)
    sector: str = Field(max_length=100)
    serial_number: Optional[str] = Field(default=None, max_length=60)


class HouseholdImport(BaseModel):
    """A CSV file as text. apply=False only previews it."""
    csv: str = Field(max_length=2_000_000)
    apply: bool = False


class HouseholdImportRow(BaseModel):
    line: int
    meter_id: str
    name: str
    action: str                 # new, update, unchanged, error
    errors: List[str] = []
    changes: List[str] = []


class HouseholdImportResult(BaseModel):
    new: int
    update: int
    unchanged: int
    error: int
    applied: bool
    rows: List[HouseholdImportRow]


class MeterCorrectionRequest(BaseModel):
    """Staff set a meter's current reading (a replaced meter, or a wrong record)."""
    reading_m3: float = Field(ge=0, le=99_999.999, allow_inf_nan=False)
    reason: str = Field(min_length=3, max_length=200)


class MeterCorrectionOut(BaseModel):
    id: int
    status: str  # applied, awaiting_approval, declined or stale
    customer_id: str
    customer_name: Optional[str] = None
    meter_id: str
    current_m3: float
    reading_m3: float
    reason: str
    requested_by: str
    requested_at: datetime
    decided_by: Optional[str] = None
    decided_at: Optional[datetime] = None
    decision_reason: Optional[str] = None


class MeterCorrectionDecline(BaseModel):
    reason: str = Field(min_length=3, max_length=200)


class PaymentStatementUpload(BaseModel):
    csv: str = Field(min_length=1, max_length=2_000_000)


class PaymentStatementOut(BaseModel):
    added: int
    updated: int
    errors: List[str] = []


class PaymentOut(BaseModel):
    """One attempt to pay a bill. status: pending (waiting for the payer's PIN, or for an officer to
    check a MoMo Pay payment), successful, failed."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    bill_id: int
    provider: str                 # momo, momo_sandbox, momo_pay, simulated
    status: str
    amount: float
    currency: str
    transaction_id: Optional[str] = None
    reason: Optional[str] = None
    already_paid: bool = False
    # momo_pay: what to dial (None until MOMO_PAY_CODE is set), WASAC's merchant code, and the
    # reference to quote (the bill number).
    ussd_code: Optional[str] = None
    pay_code: Optional[str] = None
    reference: Optional[str] = None


class PaymentReference(BaseModel):
    """The transaction ID from MTN's SMS after paying by MoMo Pay."""
    transaction_id: str = Field(min_length=4, max_length=40, pattern=r"^[A-Za-z0-9.\-]+$")


class PaymentDecline(BaseModel):
    reason: str = Field(min_length=3, max_length=120)


class PaymentToCheck(BaseModel):
    """A payment for the staff Payments page: a MoMo Pay payment waiting for an officer
    (momo_pay_check), or a second successful payment on a bill that was already paid (paid_twice,
    for information: the household paid more than once)."""
    kind: Literal["momo_pay_check", "paid_twice", "needs_reconciliation"] = "momo_pay_check"
    reason: Optional[str] = None
    # Against the uploaded payments list: None when no list exists, or the row is not a MoMo Pay check.
    statement: Optional[str] = None
    id: int
    bill_id: int
    customer_id: str
    customer_name: str
    meter_id: Optional[str] = None
    amount: float
    transaction_id: Optional[str] = None
    created_at: datetime
    submitted_at: datetime


class PaymentReconcile(BaseModel):
    outcome: Literal["paid", "failed"]
    evidence: str = Field(min_length=10, max_length=160)  # what was seen in MTN's records, and where
    transaction_id: Optional[str] = Field(default=None, min_length=3, max_length=64, pattern=r"^[A-Za-z0-9._-]+$")


class BillCorrectionRequest(BaseModel):
    corrected_reading: str = Field(max_length=20)
    # A first bill measured from nothing: the meter's true starting reading (equal to
    # corrected_reading: that reading was only ever the starting point, nothing is owed).
    start_reading: Optional[str] = Field(default=None, max_length=20)
    reason: str = Field(min_length=5, max_length=200)
    request_key: Optional[str] = Field(default=None, max_length=64)  # the same key twice is one correction
    apply: bool = True  # False: show the effect, store nothing


class BillCorrectionDecline(BaseModel):
    reason: str = Field(min_length=3, max_length=200)


class AdjustmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    bill_id: int
    consumption_before: float
    consumption_after: float
    amount_before: float
    amount_after: float
    amount_delta: float
    tariff_version: str


class BillCorrectionOut(BaseModel):
    id: Optional[int] = None  # none on a preview
    status: str               # preview, applied, awaiting_approval, declined, stale
    customer_id: str
    customer_name: Optional[str] = None
    reading_id: int
    value_before_m3: float
    corrected_value_m3: float
    kind: str = "reading"
    start_m3: Optional[float] = None
    reason: str
    requested_by: str
    decided_by: Optional[str] = None
    decision_reason: Optional[str] = None
    created_at: Optional[datetime] = None
    decided_at: Optional[datetime] = None
    needs_approval: bool = False
    net_delta: float = 0.0
    adjustments: List[AdjustmentOut] = []
