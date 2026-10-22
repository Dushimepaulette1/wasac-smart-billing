"""SMS sent through the Africa's Talking sandbox, for admins to read in the staff area.

The sandbox never delivers to real phones, and its simulator is not always available, so the
messages are kept here (newest SMS_OUTBOX_KEEP, default 200). Only sandbox messages: live SMS
are never stored. Sign-in codes appear here in plain text, which is why only admins can read it.
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String

from app.db.session import Base


class SmsOutbox(Base):
    __tablename__ = "sms_outbox"

    id = Column(Integer, primary_key=True, autoincrement=True)
    at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    phone = Column(String(20), nullable=False)
    message = Column(String(480), nullable=False)
    status = Column(String(40), nullable=False)  # "sent", or Africa's Talking's reason
