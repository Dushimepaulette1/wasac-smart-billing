"""When may a household send a reading? One reading per billing period, one at a time.

    pending    a reading is waiting for an officer: wait for the decision
    too_soon   a reading was accepted less than MIN_DAYS_BETWEEN_READINGS days ago (default 25):
               the next one opens on `opens_on`

Households only; staff can always enter a reading (for example a field officer at the meter).
A rejected reading does not count: the household is asked to read again straight away.
MIN_DAYS_BETWEEN_READINGS=0 turns the period rule off (for testing).
"""
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.anomaly.statuses import READING_FLAGGED, READING_PENDING, READING_VALID
from app.models import Meter, Reading

PENDING = "pending"
TOO_SOON = "too_soon"


@dataclass
class ReadingBlock:
    reason: str                          # PENDING or TOO_SOON
    opens_on: Optional[datetime] = None  # TOO_SOON: when the next reading may be sent

    @property
    def message(self) -> str:
        if self.reason == PENDING:
            return "Your last reading is still being checked. You can send a new one after the decision."
        return f"This period's reading is already in. The next one opens on {self.opens_on:%d/%m/%Y}."


def min_days_between_readings() -> int:
    try:
        return max(0, int(os.getenv("MIN_DAYS_BETWEEN_READINGS", "25")))
    except ValueError:
        return 25


def reading_block(db: Session, meter: Meter, now: Optional[datetime] = None) -> Optional[ReadingBlock]:
    """Why this meter cannot take a new household reading now, or None if it can."""
    now = now or datetime.utcnow()
    pending = (
        db.query(Reading.reading_id)
        .filter(Reading.meter_id == meter.meter_id, Reading.validation_status == READING_PENDING)
        .first()
    )
    if pending:
        return ReadingBlock(PENDING)
    days = min_days_between_readings()
    if not days:
        return None
    # The last reading that was accepted and billed (not meters.last_reading_date, which a new
    # meter gets at creation even with no reading yet).
    last = (
        db.query(func.max(Reading.submission_time))
        .filter(
            Reading.meter_id == meter.meter_id,
            Reading.validation_status.in_((READING_VALID, READING_FLAGGED)),
            Reading.submission_method != "correction",  # a staff correction is not this period's reading
        )
        .scalar()
    )
    if last and now - last < timedelta(days=days):
        return ReadingBlock(TOO_SOON, opens_on=last + timedelta(days=days))
    return None
