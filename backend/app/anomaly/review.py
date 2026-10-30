"""WASAC staff decisions on flagged readings: accept a pending reading, reject it, or just close the flag."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models import AnomalyFlag, FLAG_STATUS_RESOLVED
from app.anomaly.location import env_float
from app.anomaly.readings import rollover_consumption
from app.anomaly.notifications import RESUBMIT_MESSAGE, confirmed_message, sms_household, starting_point_message
from app.anomaly.service import has_baseline, household_phone, lock_meter
from app.anomaly.statuses import NOT_CONFIRMED, READING_PENDING, READING_REJECTED, READING_VALID
from app.models import Bill, Customer, Meter, Reading, ReadingEvidence
from app.services.balance import settle
from app.services.billing import build_bill
from app.services.push import send_to_phone

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


def _accept(db: Session, reading: Reading) -> Optional[Bill]:
    """Confirm a pending reading and bill it. A meter with no starting value yet (has_baseline) gets
    this reading as its starting point instead, with no bill: there is nothing to measure it from."""
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

    meter = lock_meter(db, reading.meter_id)
    if not has_baseline(db, meter):
        reading.validation_status = READING_VALID
        reading.implied_consumption = None
        meter.last_reading = reading.submitted_value
        meter.last_reading_date = reading.submission_time
        return None
    # Accepting a lower reading (e.g. a replaced meter) resets the baseline and bills nothing for this period.
    consumption = rollover_consumption(meter.last_reading, reading.submitted_value)
    if consumption is None:
        consumption = max(0.0, reading.submitted_value - meter.last_reading)
    reading.validation_status = READING_VALID
    reading.implied_consumption = consumption
    customer_id = db.query(Customer.customer_id).filter(Customer.meter_id == reading.meter_id).scalar()
    bill = build_bill(customer_id, reading.reading_id, consumption)
    db.add(bill)
    meter.last_reading = reading.submitted_value
    meter.last_reading_date = reading.submission_time
    settle(db, customer_id)  # any credit goes towards the new bill
    return bill


def _save_meter_location(db: Session, reading: Reading) -> bool:
    """A meter with no location on file gets the location of the first camera photo an officer
    accepts, if the phone's fix was precise enough. Later readings are checked against it."""
    meter = db.get(Meter, reading.meter_id)
    if meter is None or meter.gps_lat is not None:
        return False
    evidence = db.get(ReadingEvidence, reading.reading_id)
    max_accuracy = env_float("LOCATION_SAVE_MAX_ACCURACY_M", 100.0)
    if (
        evidence is None
        or evidence.photo_source != "camera"
        or evidence.lat is None
        or evidence.lng is None
        or (evidence.accuracy_m is not None and evidence.accuracy_m > max_accuracy)
    ):
        return False
    meter.gps_lat, meter.gps_lng = evidence.lat, evidence.lng
    return True


def decision_alert(outcome: str, amount_due: Optional[float]) -> tuple[str, str, str]:
    """(title, body, url) of the phone alert: Kinyarwanda first, then English (the server does
    not know the household's language). Kinyarwanda drafts: docs/i18n/kinyarwanda_review_push.csv."""
    if outcome == ACCEPT and amount_due is None:  # a first reading, recorded as the starting point
        return (
            "Mubazi: igipimo cya mbere cyanditswe",
            "Igipimo cyawe cya mbere cyanditswe nk'aho tuzahera. Fagitire ya mbere izaza n'igipimo gikurikira."
            "\nYour first reading is recorded as your starting point. Your first bill comes with your next reading.",
            "/messages",
        )
    if outcome == ACCEPT:
        amount = f"RWF {amount_due:,.0f}"
        return (
            "Mubazi: igipimo cyemejwe",
            f"Fagitire yawe ni {amount}. Kanda wishyure.\nYour reading was accepted. Bill: {amount}.",
            "/history",
        )
    return (
        "Mubazi: ongera usome mubazi",
        "Ntitwashoboye kwemeza igipimo cyawe. Ohereza indi foto.\nPlease read your meter again.",
        "/submit/camera",
    )


def resolve_flag(db: Session, flag: AnomalyFlag, outcome: Optional[str]) -> Resolution:
    """Close a flag. A flag on a pending reading needs an outcome; other flags must not have one.

    The flag and its reading are read again under a row lock, so when two officers decide at once
    the second sees the first's decision (409) instead of billing the reading a second time."""
    flag = (
        db.query(AnomalyFlag).filter(AnomalyFlag.id == flag.id).with_for_update().populate_existing().one()
    )
    reading = (
        db.query(Reading).filter(Reading.reading_id == flag.reading_id).with_for_update().populate_existing().first()
        if flag.reading_id
        else None
    )
    if outcome is not None and flag.status == FLAG_STATUS_RESOLVED:
        raise ReviewError(409, "Another officer has already decided this reading.")
    pending = reading is not None and reading.validation_status == READING_PENDING

    if pending and outcome is None:
        raise ReviewError(422, "This reading is pending review: outcome must be 'accept' or 'reject'.")
    if outcome is not None and not pending:
        raise ReviewError(409, "Only flags on a pending reading can be accepted or rejected.")

    resolution = Resolution(outcome=outcome, reading_status=reading.validation_status if reading else None)
    if outcome == ACCEPT:
        resolution.bill = _accept(db, reading)
        if _save_meter_location(db, reading):
            resolution.actions.append("meter_location_saved")
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
            if outcome == ACCEPT and resolution.bill is None:
                message = starting_point_message(reading.submitted_value)
            elif outcome == ACCEPT:
                message = confirmed_message(reading.submitted_value, resolution.bill.amount_due)
            else:
                message = RESUBMIT_MESSAGE
            resolution.actions.append(sms_household(phone, message))
            title, body, url = decision_alert(outcome, resolution.bill.amount_due if resolution.bill else None)
            if send_to_phone(db, phone, title, body, url):
                resolution.actions.append("push_household_sent")
    return resolution
