"""One attempt to pay a bill (app/services/payments.py). A bill can have several attempts (a declined
one, then a successful one); a pending attempt is reused rather than asking MTN twice."""
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String

from app.db.session import Base

PENDING, SUCCESSFUL, FAILED = "pending", "successful", "failed"


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bill_id = Column(Integer, ForeignKey("bills.bill_id"), nullable=False, index=True)
    provider = Column(String(20), nullable=False)        # momo, momo_sandbox, momo_pay, simulated
    reference_id = Column(String(64), nullable=False, unique=True)  # our id, sent to MTN as X-Reference-Id
    status = Column(String(12), nullable=False, default=PENDING)
    amount = Column(Float, nullable=False)
    currency = Column(String(3), nullable=False)
    transaction_id = Column(String(64), nullable=True)   # MTN's financialTransactionId, or the MoMo Pay ID the payer typed
    reason = Column(String(120), nullable=True)          # why it failed, in MTN's words
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
