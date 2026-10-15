"""Household sign-in with a one-time SMS code, and who may see which household.

    POST /household/request-code   {phone}           send a 6-digit code (same answer for any number)
    POST /household/verify         {phone, code}     a 30-day household token
    GET  /household/me                               the accounts registered to that phone

A household token is for a phone number: it opens every account registered to
that number (a landlord may have several meters). Staff tokens open every
household. `household_access` is the dependency for household endpoints.

Codes go out by SMS through Africa's Talking (anomaly/notifications.py). DEMO-
households have no real phones, so their codes are also returned in the
response and shown on screen; codes for real households are never shown or
logged.
"""
import logging
import os
import re
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy.orm import Session

from anomaly.notifications import send_sms, sms_configured
from auth.models import HouseholdCode, StaffUser
from auth.security import hash_code, make_token, read_token
from database import Customer, Meter, get_db
from ratelimit import RateLimiter, client_ip

router = APIRouter(prefix="/household")
logger = logging.getLogger(__name__)

CODE_TTL = timedelta(minutes=10)
RESEND_AFTER_SECONDS = 60
MAX_CODES_PER_PHONE = 3          # in CODE_WINDOW
CODE_WINDOW = timedelta(minutes=15)
MAX_ATTEMPTS = 5                 # wrong tries per code
SESSION_TTL = 30 * 24 * 60 * 60  # households stay signed in for 30 days on their phone
SUBJECT_PREFIX = "household:"
DEMO_PREFIX = "DEMO-"
WRONG_CODE = "That code is not right, or it has expired. Ask for a new code."

# Per IP, on top of the per-phone limit: stops one caller sending SMS to many numbers.
_request_limiter = RateLimiter(5, 15 * 60)
_verify_limiter = RateLimiter(20, 15 * 60)


def reset_household_limits() -> None:
    """For tests."""
    for limiter in (_request_limiter, _verify_limiter):
        limiter.reset()


def normalize_phone(raw: str) -> Optional[str]:
    """A Rwandan mobile number as +2507XXXXXXXX, or None.
    Accepts 0788 123 456, 788123456, 250788123456 and +250 788-123-456."""
    digits = re.sub(r"[\s\-().]", "", raw or "")
    if digits.startswith("+"):
        digits = digits[1:]
    if not digits.isdigit():
        return None
    if digits.startswith("250"):
        digits = digits[3:]
    elif digits.startswith("0"):
        digits = digits[1:]
    return f"+250{digits}" if re.fullmatch(r"7\d{8}", digits) else None


def _customers_for(db: Session, phone: str) -> List[Customer]:
    return db.query(Customer).filter(Customer.phone == phone).order_by(Customer.customer_id).all()


class CodeRequest(BaseModel):
    phone: str


class CodeSent(BaseModel):
    phone: str
    expires_in: int
    resend_after: int
    # Only for DEMO- households while SMS is not wired; never for a real household.
    demo_code: Optional[str] = None


class VerifyRequest(BaseModel):
    phone: str
    code: str


class HouseholdAccount(BaseModel):
    customer_id: str
    name: str
    meter_id: Optional[str]
    sector: Optional[str]
    is_demo: bool


class HouseholdSession(BaseModel):
    access_token: str
    expires_at: int
    phone: str
    accounts: List[HouseholdAccount]


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
    customers = _customers_for(db, phone)
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
    customers = _customers_for(db, phone)
    if not customers:
        raise HTTPException(status_code=400, detail=WRONG_CODE)
    token, expires_at = make_token(SUBJECT_PREFIX + phone, ttl=SESSION_TTL)
    return HouseholdSession(access_token=token, expires_at=expires_at, phone=phone, accounts=_accounts(customers))


# ---- Who may see what ------------------------------------------------------


@dataclass
class Access:
    """The caller: a staff member (sees every household) or a household phone."""
    staff: Optional[StaffUser] = None
    phone: Optional[str] = None
    customers: List[Customer] = field(default_factory=list)

    def owns_customer(self, customer_id: str) -> bool:
        return self.staff is not None or any(c.customer_id == customer_id for c in self.customers)

    def owns_meter(self, meter_id: str) -> bool:
        return self.staff is not None or any(c.meter_id == meter_id for c in self.customers)

    def require_customer(self, customer_id: str) -> None:
        # 404, not 403: a household cannot learn that someone else's account exists.
        if not self.owns_customer(customer_id):
            raise HTTPException(status_code=404, detail="Customer not found")

    def require_meter(self, meter_id: str) -> None:
        if not self.owns_meter(meter_id):
            raise HTTPException(status_code=404, detail="Meter not found")


def _signed_out() -> HTTPException:
    return HTTPException(status_code=401, detail="Sign in to continue.", headers={"WWW-Authenticate": "Bearer"})


def household_access(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> Access:
    """Dependency for household endpoints: a household or a staff token."""
    scheme, _, token = (authorization or "").partition(" ")
    subject = read_token(token) if scheme.lower() == "bearer" and token else None
    if not subject:
        raise _signed_out()
    if subject.startswith(SUBJECT_PREFIX):
        phone = subject[len(SUBJECT_PREFIX):]
        customers = _customers_for(db, phone)
        if not customers:
            raise _signed_out()
        return Access(phone=phone, customers=customers)
    staff = db.query(StaffUser).filter(StaffUser.username == subject).first()
    if not staff or not staff.is_active:
        raise _signed_out()
    return Access(staff=staff)


@router.get("/me", response_model=List[HouseholdAccount])
async def me(access: Access = Depends(household_access)):
    if access.staff is not None:
        raise HTTPException(status_code=400, detail="This is for households.")
    return _accounts(access.customers)


def meter_for(db: Session, access: Access, meter_id: str) -> Meter:
    access.require_meter(meter_id)
    meter = db.query(Meter).filter(Meter.meter_id == meter_id).first()
    if not meter:
        raise HTTPException(status_code=404, detail="Meter not found")
    return meter
