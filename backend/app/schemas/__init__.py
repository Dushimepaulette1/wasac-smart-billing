"""Every request and response shape (Pydantic), in one place: `from app.schemas import CustomerInfo`.

FastAPI checks each request body against these and turns each response into JSON with them.

    reading.py         photo reading, live tips, confirming a reading
    billing.py         bills, tariff breakdown, household details
    anomaly.py         flags, review queue, decisions
    staff_auth.py      staff sign-in, accounts, activity log
    household_auth.py  household SMS sign-in
    system.py          health check, USSD
"""
from app.schemas.anomaly import (  # noqa: F401
    AnomalyResultSchema,
    AnomalyScoreRequest,
    AnomalyFlagOut,
    ResolveFlagRequest,
    ResolveFlagResponse,
    HistoryPoint,
    ReviewItem,
)
from app.schemas.billing import (  # noqa: F401
    TariffBreakdown,
    BillCalculateRequest,
    CustomerInfo,
)
from app.schemas.household_auth import (  # noqa: F401
    CodeRequest,
    CodeSent,
    VerifyRequest,
    HouseholdAccount,
    HouseholdSession,
)
from app.schemas.reading import (  # noqa: F401
    PhotoSubmitResponse,
    NormalizedBox,
    GuideFrameResponse,
    GeoPoint,
    ConfirmReadingRequest,
    ConfirmReadingResponse,
)
from app.schemas.staff_auth import (  # noqa: F401
    LoginRequest,
    StaffUserOut,
    LoginResponse,
    StaffActionOut,
    StaffAccountOut,
    StaffAccountCreate,
    StaffAccountUpdate,
    TemporaryPasswordResponse,
    ChangePasswordRequest,
)
from app.schemas.system import (  # noqa: F401
    HealthResponse,
    USSDRequest,
)
