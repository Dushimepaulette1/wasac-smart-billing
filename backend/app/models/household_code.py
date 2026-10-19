"""One-time SMS sign-in codes for households (app/api/routes/household_auth.py)."""
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String

from app.db.session import Base


class HouseholdCode(Base):
    """A one-time sign-in code sent by SMS to a household's phone. Only a keyed
    hash of the code is stored; a code works once, for a few minutes, and only
    for a few wrong tries."""

    __tablename__ = "household_codes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    phone = Column(String(20), nullable=False, index=True)
    code_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    expires_at = Column(DateTime, nullable=False)
    attempts = Column(Integer, nullable=False, default=0)
    used_at = Column(DateTime, nullable=True)
