"""What the photo reader saw, kept so an officer can check a held reading (app/services/photo_evidence.py)."""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, LargeBinary, String

from app.db.session import Base


class PhotoRead(Base):
    """One photo sent to /submit-photo: the image, what the models read, and, once the household
    confirms, the reading it belongs to and whether they changed the digits.

    The id is random and unguessable; only the caller who sent the photo can link it to a reading,
    and only staff can see it afterwards. Images are deleted after PHOTO_RETENTION_DAYS."""

    __tablename__ = "photo_reads"

    id = Column(String(32), primary_key=True)
    owner = Column(String(64), nullable=False)  # "household:+250..." or "staff:<username>"
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    image_jpeg = Column(LargeBinary, nullable=True)  # None once the retention period has passed
    reader_digits = Column(String(16), nullable=True)  # 8 digits, or None if nothing could be read
    confidence_min = Column(Float, nullable=True)
    confidence_mean = Column(Float, nullable=True)
    quality_score = Column(Float, nullable=True)
    crop_method = Column(String(16), nullable=True)
    guidance = Column(String(200), nullable=True)  # codes, comma-separated
    models = Column(String(200), nullable=True)  # model files that read it, e.g. "best.onnx, meter_reader.onnx"
    reading_id = Column(Integer, ForeignKey("readings.reading_id"), nullable=True, unique=True)
    edited = Column(Boolean, nullable=True)  # the household changed the reader's digits
