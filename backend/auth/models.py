from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String

from database import Base

# What each role can do (checked by require_role in auth/routes.py):
#   officer     review readings, see households, see their own activity
#   supervisor  as officer, plus everyone's activity
#   admin       as supervisor, plus staff accounts
ROLES = ("officer", "supervisor", "admin")


class StaffUser(Base):
    """A WASAC staff member who can sign in to the staff dashboard."""

    __tablename__ = "staff_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False, default="officer")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class StaffAction(Base):
    """Audit log: one row per sign-in, review decision or account change.
    Rows are only ever added, never edited or deleted by the API."""

    __tablename__ = "staff_actions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    username = Column(String(64), nullable=False, index=True)
    # sign_in, sign_in_failed, accept, reject, close, account_created,
    # account_updated, password_reset, password_changed
    action = Column(String(32), nullable=False)
    target = Column(String(64), nullable=True)  # flag id, username, ...
    detail = Column(String(200), nullable=True)
    ip = Column(String(64), nullable=True)
