"""Storing a reading: lock the meter, evaluate it, then bill it or hold it for an officer.

    app/anomaly/scoring.py      rules and model, on the household's history
    app/anomaly/evaluation.py   every check, read-only
"""
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.anomaly.evaluation import (  # noqa: F401  (imported from here by routes and tests)
    DUPLICATE_WINDOW,
    Evaluation,
    ReadingRefused,
    evaluate_reading,
    has_baseline,
    review_reason,
)
from app.anomaly.location import PhotoEvidence
from app.anomaly.notifications import dispatch, sms_household
from app.anomaly.rules import AnomalyType
from app.anomaly.scoring import (  # noqa: F401
    AnomalyResult,
    assess,
    load_history,
    save_flag,
    score_reading,
    score_submission,
    since_last_reset,
)
from app.anomaly.statuses import READING_FLAGGED, READING_PENDING, READING_VALID
from app.models import Bill, Customer, Meter, PhotoRead, Reading, ReadingEvidence
from app.services.balance import settle
from app.services.billing import build_bill
from app.services.photo_evidence import link_photo


def lock_meter(db: Session, meter_id: str) -> Meter:
    """The meter row, locked until commit (Postgres SELECT ... FOR UPDATE; SQLite has no row
    locks and runs one writer at a time anyway). Two readings or decisions for one meter then
    run one after the other, each seeing the other's last_reading, never the same old baseline."""
    return (
        db.query(Meter)
        .filter(Meter.meter_id == meter_id)
        .with_for_update()
        .populate_existing()
        .one()
    )


@dataclass
class Submission:
    reading: Reading
    anomaly: AnomalyResult
    consumption_m3: float
    bill: Optional[Bill] = None


def submit_reading(
    db: Session,
    meter: Meter,
    customer_id: Optional[str],
    reading_m3: float,
    method: str,
    evidence: Optional[PhotoEvidence] = None,
    household: bool = False,
    photo: Optional[PhotoRead] = None,
) -> Submission:
    """Store a household reading, score it, and either confirm and bill it or hold it for staff review.

    The meter is locked first, then evaluate_reading runs every check: a household (household=True)
    must be allowed to send a reading now (app/services/reading_window.py), and nobody may send the
    same value twice within DUPLICATE_WINDOW. Either raises ReadingRefused with nothing stored.

    Held readings (MISREAD_SUSPECTED, SPIKE, anything below the last confirmed reading, or a photo
    whose location or source needs checking, see app/anomaly/location.py) are not billed and do not move
    meters.last_reading. photo (the caller's own, from photo_evidence.claim) is linked to the reading
    in the same transaction. Commits; call notify_household afterwards.
    """
    now = datetime.utcnow()
    meter = lock_meter(db, meter.meter_id)
    evaluation = evaluate_reading(db, meter, reading_m3, now, evidence=evidence, household=household, photo=photo)
    if evaluation.refusal:
        db.rollback()
        raise evaluation.refusal

    consumption = evaluation.consumption_m3
    reading = Reading(
        meter_id=meter.meter_id,
        submitted_value=reading_m3,
        implied_consumption=consumption,
        submission_method=method,
        submission_time=now,
    )
    db.add(reading)
    db.flush()

    scored, anomaly = evaluation.scored, evaluation.anomaly
    if scored.is_anomaly:
        save_flag(db, scored, reading.reading_id)
    if anomaly is not scored:
        save_flag(db, anomaly, reading.reading_id)
    check = evaluation.location
    if check is not None:
        db.add(ReadingEvidence(
            reading_id=reading.reading_id, photo_source=evidence.photo_source, lat=evidence.lat, lng=evidence.lng,
            accuracy_m=evidence.accuracy_m, distance_m=check.distance_m, outcome=check.outcome,
        ))

    if photo is not None:
        link_photo(photo, reading, evaluation.edit.household_digits)

    reading.anomaly_score = anomaly.anomaly_score
    submission = Submission(reading=reading, anomaly=anomaly, consumption_m3=consumption)
    if anomaly.pending_review:
        reading.validation_status = READING_PENDING
    else:
        reading.validation_status = READING_FLAGGED if anomaly.is_anomaly else READING_VALID
        submission.bill = build_bill(customer_id, reading.reading_id, consumption)
        db.add(submission.bill)
        meter.last_reading = reading_m3
        meter.last_reading_date = now
        settle(db, customer_id)  # any credit goes towards the new bill
    db.commit()
    if submission.bill is not None:
        db.refresh(submission.bill)
    return submission


def household_phone(db: Session, household_id: str) -> Optional[str]:
    return db.query(Customer.phone).filter(Customer.meter_id == household_id).scalar()


def notify_household(db: Session, result: AnomalyResult) -> List[str]:
    """Send the notifications for a flagged result. Call after the transaction commits."""
    if not result.is_anomaly:
        return []
    phone = household_phone(db, result.household_id)
    if result.needs_retake:
        if not phone:
            return []
        return [sms_household(phone, result.message_for_household)]
    return dispatch(AnomalyType(result.anomaly_type), phone, result.message_for_household)
