"""One attempt to pay a bill (app/services/payments.py). A bill can have several attempts (a declined
one, then a successful one); a pending attempt is reused rather than asking MTN twice."""
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, String, text

from app.db.session import Base

PENDING, SUCCESSFUL, FAILED = "pending", "successful", "failed"
MOMO_PAY = "momo_pay"


class Payment(Base):
    __tablename__ = "payments"
    # At most one open attempt per bill, and one MoMo Pay transaction ID per payment (a declined
    # attempt frees its ID). app/db/init_db.py adds them to older databases.
    __table_args__ = (
        Index("uq_payments_one_pending", "bill_id", unique=True,
              sqlite_where=text("status = 'pending'"), postgresql_where=text("status = 'pending'")),
        Index("uq_payments_momo_pay_txn", "transaction_id", unique=True,
              sqlite_where=text("provider = 'momo_pay' AND status <> 'failed'"),
              postgresql_where=text("provider = 'momo_pay' AND status <> 'failed'")),
    )

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
    # A second success on a paid bill, looked at by staff (it stays on record, off their list).
    reviewed_by = Column(String(64), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)


class PaymentStatementEntry(Base):
    """A payment WASAC received, from an uploaded list. Synthetic until WASAC shares real records
    (app/services/payment_statement.py)."""
    __tablename__ = "payment_statement_entries"

    transaction_id = Column(String(64), primary_key=True)
    amount = Column(Float, nullable=False)
    reference = Column(String(64))  # the meter serial or bill the payer quoted
    uploaded_by = Column(String, nullable=False)
    uploaded_at = Column(DateTime, nullable=False, default=datetime.utcnow)
