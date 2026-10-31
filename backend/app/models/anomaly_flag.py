"""Flags: "something about this reading looks odd" (a leak, a misread, a photo taken elsewhere).
Written by app/anomaly/service.py, shown to households in Messages and to officers in the review queue."""
from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, ForeignKey, Integer, String

from app.db.session import Base

FLAG_STATUS_OPEN = "open"
FLAG_STATUS_RESOLVED = "resolved"


class AnomalyFlag(Base):
    """One row per flagged submission. household_id is the meter_id readings are stored under."""

    __tablename__ = "anomaly_flags"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    household_id = Column(String, ForeignKey("meters.meter_id"), index=True, nullable=False)
    reading_id = Column(Integer, ForeignKey("readings.reading_id"), nullable=True)
    anomaly_type = Column(String, nullable=False, index=True)
    anomaly_score = Column(Float)
    features = Column(JSON)
    requires_staff_review = Column(Boolean, default=False, nullable=False)
    message_for_household = Column(String)
    status = Column(String, default=FLAG_STATUS_OPEN, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = Column(DateTime, nullable=True)
    # Why it was rejected, as a code the household's app can word (the officer's own text stays staff-only).
    decision_code = Column(String(16), nullable=True)


class MessageDismissal(Base):
    """The household deleted this message from its Messages list. The flag itself stays for staff
    and the audit trail; only the household's view hides it."""

    __tablename__ = "message_dismissals"

    flag_id = Column(Integer, ForeignKey("anomaly_flags.id"), primary_key=True)
    dismissed_at = Column(DateTime, nullable=False, default=datetime.utcnow)
