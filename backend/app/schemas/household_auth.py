"""Household sign-in with a one-time SMS code (app/api/routes/household_auth.py)."""
from typing import List, Optional

from pydantic import BaseModel


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
