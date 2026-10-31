"""Staff correct a meter's current reading: a replaced meter, or WASAC's record was wrong.

The corrected value is stored as a reading (submission_method "correction", status valid, no
bill) so it becomes the meter's new starting point: the next household reading is compared with
it, and history before it is set aside (app/anomaly/service.py since_last_reset). It does not
count as this period's reading, so the household can read straight away
(app/services/reading_window.py). Every correction is in the activity log; who may ask and who
approves is in app/services/meter_correction_requests.py.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.anomaly.statuses import READING_PENDING, READING_VALID
from app.models import Meter, Reading

CORRECTION = "correction"
MAX_READING_M3 = 99_999.999  # 5 cubic-metre wheels, 3 litre wheels


class CorrectionError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def reading_in_review(db: Session, meter: Meter) -> bool:
    return (
        db.query(Reading.reading_id)
        .filter(Reading.meter_id == meter.meter_id, Reading.validation_status == READING_PENDING)
        .first()
    ) is not None


def correct_meter(db: Session, meter: Meter, reading_m3: float, now: Optional[datetime] = None) -> Reading:
    """Set the meter's current reading. Commits nothing; the caller records the audit and commits."""
    if not 0 <= reading_m3 <= MAX_READING_M3:
        raise CorrectionError(422, "A meter reading is between 0 and 99999.999 m³.")
    if reading_in_review(db, meter):
        raise CorrectionError(409, "A reading from this household is waiting in the review queue: decide on it first.")
    now = now or datetime.utcnow()
    reading = Reading(
        meter_id=meter.meter_id,
        submitted_value=round(reading_m3, 3),
        implied_consumption=None,
        submission_method=CORRECTION,
        validation_status=READING_VALID,
        submission_time=now,
    )
    db.add(reading)
    meter.last_reading = round(reading_m3, 3)
    meter.last_reading_date = now
    return reading
