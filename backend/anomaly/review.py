"""WASAC staff decisions on flagged readings: accept a pending reading, reject it, or just close the flag."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from anomaly.db_models import FLAG_STATUS_RESOLVED, AnomalyFlag
from anomaly.notifications import RESUBMIT_MESSAGE, confirmed_message, send_sms
from anomaly.service import household_phone
from anomaly.statuses import NOT_CONFIRMED, READING_PENDING, READING_REJECTED, READING_VALID
from database import Bill, Customer, Meter, Reading, build_bill

ACCEPT = "accept"
REJECT = "reject"


class ReviewError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


@dataclass
class Resolution:
    outcome: Optional[str] = None
    reading_status: Optional[str] = None
    bill: Optional[Bill] = None
    actions: List[str] = field(default_factory=list)


def _accept(db: Session, reading: Reading) -> Bill:
    newer_confirmed = (
        db.query(Reading.reading_id)
        .filter(
            Reading.meter_id == reading.meter_id,
            Reading.submission_time > reading.submission_time,
            Reading.validation_status.notin_(NOT_CONFIRMED),
        )
        .first()
    )
    if newer_confirmed:
        raise ReviewError(409, "A newer reading for this meter is already confirmed; reject this one instead.")

    meter = db.get(Meter, reading.meter_id)
    # Accepting a lower reading (e.g. a replaced meter) resets the baseline and bills nothing for this period.
    consumption = max(0.0, reading.submitted_value - meter.last_reading)
    reading.validation_status = READING_VALID
    reading.implied_consumption = consumption
    customer_id = db.query(Customer.customer_id).filter(Customer.meter_id == reading.meter_id).scalar()
    bill = build_bill(customer_id, reading.reading_id, consumption)
    db.add(bill)
    meter.last_reading = reading.submitted_value
    meter.last_reading_date = reading.submission_time
    return bill


def resolve_flag(db: Session, flag: AnomalyFlag, outcome: Optional[str]) -> Resolution:
    """Close a flag. A flag on a pending reading needs an outcome; other flags must not have one."""
    reading = db.get(Reading, flag.reading_id) if flag.reading_id else None
    pending = reading is not None and reading.validation_status == READING_PENDING

    if pending and outcome is None:
        raise ReviewError(422, "This reading is pending review: outcome must be 'accept' or 'reject'.")
    if outcome is not None and not pending:
        raise ReviewError(409, "Only flags on a pending reading can be accepted or rejected.")

    resolution = Resolution(outcome=outcome, reading_status=reading.validation_status if reading else None)
    if outcome == ACCEPT:
        resolution.bill = _accept(db, reading)
    elif outcome == REJECT:
        reading.validation_status = READING_REJECTED

    if flag.status != FLAG_STATUS_RESOLVED:
        flag.status = FLAG_STATUS_RESOLVED
        flag.resolved_at = datetime.utcnow()
    db.commit()

    if reading is not None:
        resolution.reading_status = reading.validation_status
    if outcome is not None:
        phone = household_phone(db, flag.household_id)
        if phone:
            message = (
                confirmed_message(reading.submitted_value, resolution.bill.amount_due)
                if outcome == ACCEPT
                else RESUBMIT_MESSAGE
            )
            send_sms(phone, message)
            resolution.actions.append("sms_household_logged")
    return resolution
