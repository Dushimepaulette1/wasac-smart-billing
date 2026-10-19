"""All API routes in one router. app/main.py adds it to the app.

    routes/readings.py        /submit-photo, /guide-frame, /confirm-reading, /calculate-bill
    routes/billing.py         /customers, /customers/{id}/bills, /bills/{id}/pay
    routes/anomaly.py         /api/anomaly/... (messages, review queue, decisions)
    routes/household_auth.py  /household/... (SMS sign-in)
    routes/staff_auth.py      /auth/... (staff sign-in, activity, accounts)
    routes/ussd.py            /submit-ussd
    routes/health.py          /health
"""
from fastapi import APIRouter

from app.api.routes import anomaly, billing, health, household_auth, readings, staff_auth, ussd

api_router = APIRouter()
api_router.include_router(readings.router, tags=["Meter Reading"])
api_router.include_router(billing.router, tags=["Billing"])
api_router.include_router(ussd.router, tags=["USSD"])
api_router.include_router(anomaly.router, tags=["Anomaly Detection"])
api_router.include_router(staff_auth.router, tags=["Staff sign-in"])
api_router.include_router(household_auth.router, tags=["Household sign-in"])
api_router.include_router(health.router, tags=["System"])
