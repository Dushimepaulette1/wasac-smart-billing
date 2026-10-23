"""The photo behind a reading, for the officer who checks it.

    /submit-photo     save_photo_read: the photo (1280 px), what the models read  -> photo_id
    /confirm-reading  attach: link that photo to the reading the household confirmed, note
                      whether they changed the digits, copy confidence and quality onto it
    review queue      photo_for_reading: the image, for staff only

Kept PHOTO_RETENTION_DAYS (default 90) and then deleted; a photo never confirmed is deleted after
a day. Purged whenever a new photo comes in, so no scheduled job is needed.
"""
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.models import PhotoRead, Reading

UNCONFIRMED_TTL = timedelta(days=1)


def retention() -> timedelta:
    try:
        return timedelta(days=max(1, int(os.getenv("PHOTO_RETENTION_DAYS", "90"))))
    except ValueError:
        return timedelta(days=90)


def purge(db: Session, now: Optional[datetime] = None) -> None:
    now = now or datetime.utcnow()
    db.query(PhotoRead).filter(PhotoRead.reading_id.is_(None), PhotoRead.created_at < now - UNCONFIRMED_TTL).delete(
        synchronize_session=False
    )
    db.query(PhotoRead).filter(PhotoRead.image_jpeg.isnot(None), PhotoRead.created_at < now - retention()).update(
        {PhotoRead.image_jpeg: None}, synchronize_session=False
    )


def save_photo_read(db: Session, owner: str, result, models: str) -> str:
    """Store one analysed photo; returns its id for /confirm-reading. Commits."""
    purge(db)
    photo = PhotoRead(
        id=secrets.token_hex(16),
        owner=owner,
        image_jpeg=result.evidence_jpeg,
        reader_digits=result.reading_digits,
        confidence_min=result.confidence_min,
        confidence_mean=result.confidence_mean,
        quality_score=result.quality_score,
        crop_method=result.crop_method,
        guidance=",".join(result.guidance)[:200] or None,
        models=models[:200],
    )
    db.add(photo)
    db.commit()
    return photo.id


def attach(db: Session, photo_id: Optional[str], owner: str, reading: Reading, digits: str) -> bool:
    """Link the caller's own, not yet used photo to the reading. An unknown, used or someone else's
    photo is ignored (the reading stands; it just has no photo). Commits."""
    if not photo_id:
        return False
    photo = db.get(PhotoRead, photo_id)
    if photo is None or photo.owner != owner or photo.reading_id is not None:
        return False
    photo.reading_id = reading.reading_id
    photo.edited = photo.reader_digits is not None and photo.reader_digits != digits
    reading.crnn_confidence = photo.confidence_min
    reading.quality_gate_score = photo.quality_score
    db.commit()
    return True


def photo_for_reading(db: Session, reading_id: int) -> Optional[PhotoRead]:
    return db.query(PhotoRead).filter(PhotoRead.reading_id == reading_id).first()
