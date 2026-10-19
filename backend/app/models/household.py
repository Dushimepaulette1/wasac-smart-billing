"""A household (customer) and its water meter. They point at each other: a customer has a meter,
and a meter knows its customer."""
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import relationship

from app.db.session import Base


class Customer(Base):
    __tablename__ = "customers"

    customer_id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    email = Column(String)
    meter_id = Column(String, ForeignKey("meters.meter_id"))
    sector = Column(String)
    gps_lat = Column(Float)
    gps_lng = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

    meter = relationship("Meter", foreign_keys=[meter_id])
    bills = relationship("Bill", back_populates="customer")


class Meter(Base):
    __tablename__ = "meters"

    meter_id = Column(String, primary_key=True, index=True)
    customer_id = Column(String, ForeignKey("customers.customer_id"))
    meter_type = Column(String, default="Itron Flodis")
    last_reading = Column(Float, default=0.0)
    last_reading_date = Column(DateTime, default=datetime.utcnow)
    cover_condition = Column(String, default="clean")
    gps_lat = Column(Float)
    gps_lng = Column(Float)

    customer = relationship("Customer", foreign_keys=[customer_id])
    readings = relationship("Reading", back_populates="meter")
