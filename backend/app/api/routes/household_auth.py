"""Household sign-in with a one-time SMS code.

    POST /household/request-code   {phone}           send a 6-digit code (same answer for any number)
    POST /household/verify         {phone, code}     a 30-day household token
    GET  /household/me                               the accounts registered to that phone

Who may see which household (a token per phone number) is checked in app/api/deps.py.

Codes go out by SMS through Africa's Talking (app/services/sms.py). DEMO-
households have no real phones, so their codes are also returned in the
response and shown on screen; codes for real households are never shown or
logged.
"""
import logging
import os
import re
import secrets
from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.api.deps import SESSION_TTL, SUBJECT_PREFIX, Access, customers_for, household_access
from app.core.ratelimit import RateLimiter, client_ip
from app.core.security import hash_code, make_token
from app.db.session import get_db
from app.models import Customer, HouseholdCode
from app.schemas import CodeRequest, CodeSent, HouseholdAccount, HouseholdSession, VerifyRequest
from app.services.sms import send_sms, sms_configured
from app.utils.phone import normalize_phone

router = APIRouter(prefix="/household")
logger = logging.getLogger(__name__)

CODE_TTL = timedelta(minutes=10)
RESEND_AFTER_SECONDS = 60
MAX_CODES_PER_PHONE = 3          # in CODE_WINDOW
CODE_WINDOW = timedelta(minutes=15)
MAX_ATTEMPTS = 5                 # wrong tries per code
DEMO_PREFIX = "DEMO-"
WRONG_CODE = "That code is not right, or it has expired. Ask for a new code."

# Per IP, on top of the per-phone limit: stops one caller sending SMS to many numbers.
_request_limiter = RateLimiter(5, 15 * 60)
_verify_limiter = RateLimiter(20, 15 * 60)


def reset_household_limits() -> None:
    """For tests."""
    for limiter in (_request_limiter, _verify_limiter):
        limiter.reset()


def _accounts(customers: List[Customer]) -> List[HouseholdAccount]:
    return [
        HouseholdAccount(customer_id=c.customer_id, name=c.name, meter_id=c.meter_id, sector=c.sector,
                         is_demo=c.customer_id.startswith(DEMO_PREFIX))
        for c in customers
    ]


def _too_many(seconds: float) -> HTTPException:
    return HTTPException(status_code=429, detail="Too many tries. Wait a few minutes, then try again.",
                         headers={"Retry-After": str(max(1, int(seconds)))})


@router.post("/request-code", response_model=CodeSent)
async def request_code(body: CodeRequest, request: Request, db: Session = Depends(get_db)):
    phone = normalize_phone(body.phone)
    if not phone:
        raise HTTPException(status_code=422, detail="Enter a Rwandan mobile number, for example 078 123 4567.")
    wait = _request_limiter.check(client_ip(request))
    if wait:
        raise _too_many(wait)

    now = datetime.utcnow()
    recent = (
        db.query(HouseholdCode)
        .filter(HouseholdCode.phone == phone, HouseholdCode.created_at > now - CODE_WINDOW)
        .order_by(HouseholdCode.created_at.desc())
        .all()
    )
    if len(recent) >= MAX_CODES_PER_PHONE:
        raise _too_many((recent[-1].created_at + CODE_WINDOW - now).total_seconds())
    if recent and (now - recent[0].created_at).total_seconds() < RESEND_AFTER_SECONDS:
        raise _too_many(RESEND_AFTER_SECONDS - (now - recent[0].created_at).total_seconds())

    answer = CodeSent(phone=phone, expires_in=int(CODE_TTL.total_seconds()), resend_after=RESEND_AFTER_SECONDS)
    customers = customers_for(db, phone)
    if not customers:
        # Same answer as for a registered number, so the form cannot be used to
        # find out who is a WASAC customer. Nothing is stored or sent.
        return answer

    code = f"{secrets.randbelow(1_000_000):06d}"
    db.add(HouseholdCode(phone=phone, code_hash=hash_code(phone, code), created_at=now, expires_at=now + CODE_TTL))
    db.commit()
    all_demo = all(c.customer_id.startswith(DEMO_PREFIX) for c in customers)
    if all_demo and os.getenv("OTP_SHOW_DEMO_CODES", "1") != "0":
        answer.demo_code = code  # demo numbers are not real phones; an SMS is still tried below
    if sms_configured():
        text = f"WASAC: your sign-in code is {code}. It works for 10 minutes. Never share it."
        sent = await run_in_threadpool(send_sms, phone, text, sensitive=True)
        if not sent and answer.demo_code is None:
            raise HTTPException(status_code=503, detail="We could not send the SMS just now. Try again in a few minutes.")
    elif answer.demo_code is None:
        logger.warning("Sign-in code requested but SMS is not configured (AT_USERNAME/AT_API_KEY): nothing sent.")
    return answer


@router.post("/verify", response_model=HouseholdSession)
async def verify(body: VerifyRequest, request: Request, db: Session = Depends(get_db)):
    phone = normalize_phone(body.phone)
    code = re.sub(r"\D", "", body.code or "")
    wait = _verify_limiter.check(client_ip(request))
    if wait:
        raise _too_many(wait)
    if not phone or len(code) != 6:
        raise HTTPException(status_code=400, detail=WRONG_CODE)

    now = datetime.utcnow()
    latest = (
        db.query(HouseholdCode)
        .filter(HouseholdCode.phone == phone, HouseholdCode.used_at.is_(None))
        .order_by(HouseholdCode.created_at.desc())
        .first()
    )
    if not latest or latest.expires_at < now or latest.attempts >= MAX_ATTEMPTS:
        raise HTTPException(status_code=400, detail=WRONG_CODE)
    if not secrets.compare_digest(latest.code_hash, hash_code(phone, code)):
        latest.attempts += 1
        db.commit()
        raise HTTPException(status_code=400, detail=WRONG_CODE)

    latest.used_at = now
    db.commit()
    customers = customers_for(db, phone)
    if not customers:
        raise HTTPException(status_code=400, detail=WRONG_CODE)
    token, expires_at = make_token(SUBJECT_PREFIX + phone, ttl=SESSION_TTL)
    return HouseholdSession(access_token=token, expires_at=expires_at, phone=phone, accounts=_accounts(customers))


# ---- Who may see what ------------------------------------------------------


@router.get("/me", response_model=List[HouseholdAccount])
async def me(access: Access = Depends(household_access)):
    if access.staff is not None:
        raise HTTPException(status_code=400, detail="This is for households.")
    return _accounts(access.customers)
