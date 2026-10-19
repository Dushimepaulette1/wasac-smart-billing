"""Who is asking? The checks routes depend on (FastAPI `Depends(...)`).

    require_staff        a valid staff token for an active account        -> StaffUser
    require_role(role)   ... with this role or a higher one (officer < supervisor < admin)
    household_access     a household token (its phone's accounts) or a staff token -> Access
    meter_for            the meter, if the caller may see it (404 otherwise)

A household token is for a phone number: it opens every account registered to that number
(a landlord may have several meters). Staff tokens open every household.
"""
from dataclasses import dataclass, field
from typing import List, Optional

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.core.security import read_token
from app.db.session import get_db
from app.models import Customer, Meter, StaffUser
from app.models.staff import ROLES

SESSION_TTL = 30 * 24 * 60 * 60  # households stay signed in for 30 days on their phone
SUBJECT_PREFIX = "household:"


# ---- Staff ------------------------------------------------------------------

def require_staff(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> StaffUser:
    """Dependency for staff-only routes: a valid Bearer token for an active user."""
    scheme, _, token = (authorization or "").partition(" ")
    username = read_token(token) if scheme.lower() == "bearer" and token else None
    user = db.query(StaffUser).filter(StaffUser.username == username).first() if username else None
    if not user or not user.is_active:
        raise HTTPException(
            status_code=401,
            detail="Sign in to continue.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def role_at_least(user: StaffUser, role: str) -> bool:
    current = ROLES.index(user.role) if user.role in ROLES else 0
    return current >= ROLES.index(role)


def require_role(role: str):
    """Dependency factory: signed in, with this role or a higher one."""

    def dependency(user: StaffUser = Depends(require_staff)) -> StaffUser:
        if not role_at_least(user, role):
            raise HTTPException(status_code=403, detail="Your account cannot do this.")
        return user

    return dependency


# ---- Households -------------------------------------------------------------

def customers_for(db: Session, phone: str) -> List[Customer]:
    return db.query(Customer).filter(Customer.phone == phone).order_by(Customer.customer_id).all()


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
        customers = customers_for(db, phone)
        if not customers:
            raise _signed_out()
        return Access(phone=phone, customers=customers)
    staff = db.query(StaffUser).filter(StaffUser.username == subject).first()
    if not staff or not staff.is_active:
        raise _signed_out()
    return Access(staff=staff)


def meter_for(db: Session, access: Access, meter_id: str) -> Meter:
    access.require_meter(meter_id)
    meter = db.query(Meter).filter(Meter.meter_id == meter_id).first()
    if not meter:
        raise HTTPException(status_code=404, detail="Meter not found")
    return meter
