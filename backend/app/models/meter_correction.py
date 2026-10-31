"""A supervisor's request to set a meter's starting reading, and the decision on it."""
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, String, text

from app.db.session import Base

AWAITING = "awaiting_approval"
APPLIED = "applied"
DECLINED = "declined"
STALE = "stale"


class MeterCorrection(Base):
    __tablename__ = "meter_corrections"
    __table_args__ = (
        # One open request per meter, even if two supervisors ask at the same moment.
        Index("uq_meter_corrections_awaiting", "meter_id", unique=True,
              sqlite_where=text("status = 'awaiting_approval'"),
              postgresql_where=text("status = 'awaiting_approval'")),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    meter_id = Column(String, ForeignKey("meters.meter_id"), nullable=False, index=True)
    customer_id = Column(String, ForeignKey("customers.customer_id"), nullable=False)
    current_m3 = Column(Float, nullable=False)  # on record when asked: a change meanwhile makes it stale
    reading_m3 = Column(Float, nullable=False)
    reason = Column(String(200), nullable=False)
    status = Column(String(20), nullable=False, default=AWAITING)
    requested_by = Column(String, nullable=False)
    requested_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    decided_by = Column(String)
    decided_at = Column(DateTime)
    decision_reason = Column(String(200))
