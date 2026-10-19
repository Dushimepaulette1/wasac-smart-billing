"""A meter reading a household sent, and where its photo was taken.

readings.validation_status decides what happens to it (values in app/anomaly/statuses.py):
valid and anomaly_flagged are billed; pending_review waits for an officer; rejected never counts.
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db.session import Base


class Reading(Base):
    __tablename__ = "readings"

    reading_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    meter_id = Column(String, ForeignKey("meters.meter_id"))
    submitted_value = Column(Float, nullable=False)
    implied_consumption = Column(Float)
    submission_method = Column(String, default="camera")  # "camera" or "ussd"
    crnn_confidence = Column(Float)
    quality_gate_score = Column(Float)
    anomaly_score = Column(Float)
    validation_status = Column(String, default="valid")
    submission_time = Column(DateTime, default=datetime.utcnow)

    meter = relationship("Meter", back_populates="readings")
    bill = relationship("Bill", back_populates="reading", uselist=False)


class ReadingEvidence(Base):
    """Where a reading's photo was taken, and the outcome of the location check."""

    __tablename__ = "reading_evidence"

    reading_id = Column(Integer, ForeignKey("readings.reading_id"), primary_key=True)
    photo_source = Column(String(16), nullable=False)  # camera | upload
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    accuracy_m = Column(Float, nullable=True)
    distance_m = Column(Float, nullable=True)
    outcome = Column(String(16), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
