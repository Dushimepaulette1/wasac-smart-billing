"""All API routes in one router. app/main.py adds it to the app.

    routes/readings.py        /submit-photo, /guide-frame, /confirm-reading, /calculate-bill
    routes/billing.py         /customers, /customers/{id}/bills
    routes/payments.py        /bills/{id}/pay, /payments/{id}, /api/payments/... (staff checks)
    routes/bill_corrections.py  /customers/{id}/readings/{id}/correction, /bill-corrections
    routes/anomaly.py         /api/anomaly/... (messages, review queue, decisions)
    routes/household_auth.py  /household/... (SMS sign-in)
    routes/push.py            /household/push/... (phone alerts)
    routes/staff_auth.py      /auth/... (staff sign-in, activity, accounts)
    routes/ussd.py            /ussd (Africa's Talking USSD callback)
    routes/health.py          /health
"""
from fastapi import APIRouter

from app.api.routes import (
    anomaly, bill_corrections, billing, health, household_auth, payments, push, readings, staff_auth, ussd,
)

api_router = APIRouter()
api_router.include_router(readings.router, tags=["Meter Reading"])
api_router.include_router(billing.router, tags=["Billing"])
api_router.include_router(payments.router, tags=["Payments"])
api_router.include_router(bill_corrections.router, tags=["Billing"])
api_router.include_router(ussd.router, tags=["USSD"])
api_router.include_router(anomaly.router, tags=["Anomaly Detection"])
api_router.include_router(staff_auth.router, tags=["Staff sign-in"])
api_router.include_router(household_auth.router, tags=["Household sign-in"])
api_router.include_router(push.router, tags=["Phone alerts"])
api_router.include_router(health.router, tags=["System"])
