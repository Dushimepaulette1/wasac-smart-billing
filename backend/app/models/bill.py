"""A bill: the money owed for one confirmed reading, split by tariff tier (app/services/billing.py)."""
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import relationship

from app.db.session import Base


class Bill(Base):
    __tablename__ = "bills"
    # One bill per reading, enforced by the database (app/db/init_db.py adds it to older databases).
    __table_args__ = (Index("uq_bills_reading_id", "reading_id", unique=True),)

    bill_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    customer_id = Column(String, ForeignKey("customers.customer_id"))
    reading_id = Column(Integer, ForeignKey("readings.reading_id"))
    consumption_m3 = Column(Float)
    tier1_units = Column(Float, default=0.0)
    tier2_units = Column(Float, default=0.0)
    tier3_units = Column(Float, default=0.0)
    tier4_units = Column(Float, default=0.0)
    tier1_amount = Column(Float, default=0.0)
    tier2_amount = Column(Float, default=0.0)
    tier3_amount = Column(Float, default=0.0)
    tier4_amount = Column(Float, default=0.0)
    service_charge = Column(Float, default=1000.0)
    amount_due = Column(Float)
    payment_status = Column(String, default="unpaid")
    tariff_version = Column(String(40), nullable=True)  # NULL: from before versions (the original rates)
    created_at = Column(DateTime, default=datetime.utcnow)

    customer = relationship("Customer", back_populates="bills")
    reading = relationship("Reading", back_populates="bill")
