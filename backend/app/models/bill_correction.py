"""Correcting a billed reading without touching what was billed (app/services/bill_corrections.py).

Original readings, bills and payments are never changed. A correction records the new value and
why; each bill it affects gets an adjustment; money owed back to a household is a credit.
Rows here are only added; a correction's status moves on, its figures never change."""
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Index, Integer, String

from app.db.session import Base

APPLIED, AWAITING, DECLINED, STALE = "applied", "awaiting_approval", "declined", "stale"
OVERPAYMENT, USED = "overpayment", "applied"


class BillCorrection(Base):
    """One correction of one billed reading, by a supervisor. A correction that charges more
    waits for a different supervisor or admin (AWAITING); STALE: the bills changed before approval."""

    __tablename__ = "bill_corrections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(String, ForeignKey("customers.customer_id"), nullable=False, index=True)
    reading_id = Column(Integer, ForeignKey("readings.reading_id"), nullable=False, index=True)
    value_before_m3 = Column(Float, nullable=False)
    corrected_value_m3 = Column(Float, nullable=False)
    reason = Column(String(200), nullable=False)
    status = Column(String(20), nullable=False, index=True)
    requested_by = Column(String(64), nullable=False)
    decided_by = Column(String(64), nullable=True)
    decision_reason = Column(String(200), nullable=True)
    request_key = Column(String(64), nullable=False, unique=True)  # the same request twice is one correction
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    decided_at = Column(DateTime, nullable=True)


class BillAdjustment(Base):
    """What a correction does to one bill. Counts towards the balance only once its correction is APPLIED."""

    __tablename__ = "bill_adjustments"
    __table_args__ = (Index("uq_bill_adjustment", "correction_id", "bill_id", unique=True),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    correction_id = Column(Integer, ForeignKey("bill_corrections.id"), nullable=False, index=True)
    bill_id = Column(Integer, ForeignKey("bills.bill_id"), nullable=False, index=True)
    consumption_before = Column(Float, nullable=False)
    consumption_after = Column(Float, nullable=False)
    amount_before = Column(Float, nullable=False)
    amount_after = Column(Float, nullable=False)
    amount_delta = Column(Float, nullable=False)
    tiers = Column(JSON, nullable=True)  # the recalculated tier lines, with the bill's own tariff
    tariff_version = Column(String(40), nullable=False)


class AccountCredit(Base):
    """The household's credit ledger: + an overpaid bill (source_bill_id), - credit used on a bill
    (bill_id). Available credit is the sum of amount. There are no cash refunds in the app."""

    __tablename__ = "account_credits"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(String, ForeignKey("customers.customer_id"), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    kind = Column(String(16), nullable=False)
    source_bill_id = Column(Integer, ForeignKey("bills.bill_id"), nullable=True)
    bill_id = Column(Integer, ForeignKey("bills.bill_id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
