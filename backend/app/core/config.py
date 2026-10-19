"""App-wide settings read from the environment (backend/.env locally, Render's Environment live).

Feature settings stay next to the code that uses them, read when used so tests can change them:
    app/anomaly/config.py      ANOMALY_* thresholds
    app/anomaly/location.py    LOCATION_MAX_M, LOCATION_MAX_ACCURACY_M
    app/services/sms.py        AT_USERNAME, AT_API_KEY, AT_SENDER_ID
    app/api/routes/household_auth.py  OTP_SHOW_DEMO_CODES
    app/core/ratelimit.py      TRUSTED_PROXY_HOPS
    app/core/security.py       WASAC_AUTH_SECRET
    app/db/session.py          DATABASE_URL
    app/vision/config.py       ML_WEIGHTS_DIR, VISION_BACKEND
"""
import os
from typing import List, Optional


def cors_origins() -> List[str]:
    """CORS_ORIGINS: comma-separated origins, e.g. "https://wasac.vercel.app". Local dev by default."""
    raw = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
    return [origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip()]


def cors_origin_regex() -> Optional[str]:
    """Optional, e.g. for Vercel preview URLs: ^https://wasac-[a-z0-9-]+\\.vercel\\.app$"""
    return os.getenv("CORS_ORIGIN_REGEX") or None


def seed_sample_data() -> bool:
    """SEED_SAMPLE_DATA=0 on deployments: no sample customers in a shared database."""
    return os.getenv("SEED_SAMPLE_DATA", "1") != "0"
