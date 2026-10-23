"""Phones that asked for alerts (web push), for app/services/push.py."""
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String

from app.db.session import Base


class PushSubscription(Base):
    """One browser on one phone that turned alerts on. The household is its phone number, as in
    sign-in: every account on that number gets the alerts. The endpoint is the browser vendor's
    push address; p256dh and auth are the keys the message is encrypted with."""

    __tablename__ = "push_subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    phone = Column(String(20), nullable=False, index=True)
    endpoint = Column(String(1024), nullable=False, unique=True)
    p256dh = Column(String(200), nullable=False)
    auth = Column(String(100), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_sent_at = Column(DateTime, nullable=True)
