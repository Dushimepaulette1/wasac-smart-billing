from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional, Sequence

from sqlalchemy.orm import Session

from app.anomaly.config import AnomalyConfig
from app.models import AnomalyFlag, FLAG_STATUS_OPEN
from app.anomaly.features import ReadingPoint, compute_features
from app.anomaly.location import LocationCheck, PhotoEvidence, check_location
from app.models import ReadingEvidence
from app.anomaly.model import AnomalyModel, load_model_if_available
from app.anomaly.notifications import RETAKE_MESSAGE, action_for, dispatch, message_for, sms_household
from app.anomaly.readings import digits_to_m3
from app.anomaly.rules import AnomalyType, apply_rules, classify_model_anomaly, is_cold_start
from app.anomaly.statuses import (
    NOT_CONFIRMED,
    PENDING_REVIEW_TYPES,
    READING_FLAGGED,
    READING_PENDING,
    READING_REJECTED,
    READING_VALID,
)
from app.models import Bill, Customer, Meter, Reading
from app.services.billing import build_bill
from app.services.reading_window import ReadingBlock, reading_block

# The same value for the same meter again within this time is a retry or a double tap, not a reading.
DUPLICATE_WINDOW = timedelta(minutes=2)


class ReadingRefused(Exception):
    """The reading was not stored: the household must wait (block), or it was just sent (duplicate)."""

    def __init__(self, message: str, block: Optional[ReadingBlock] = None):
        super().__init__(message)
        self.message = message
        self.block = block


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
class AnomalyResult:
    household_id: str
    reading_m3: Optional[float]
    daily_consumption: Optional[float]
    anomaly_score: Optional[float]
    is_anomaly: bool
    anomaly_type: str
    needs_retake: bool
    message_for_household: str
    features: dict = field(default_factory=dict)
    model_used: bool = False
    flag_id: Optional[int] = None
    # True when the reading must wait for WASAC staff before it is confirmed or billed.
    pending_review: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def assess(
    household_id: str,
    history: Sequence[ReadingPoint],
    reading_m3: float,
    reading_date: datetime,
    model: Optional[AnomalyModel],
    config: AnomalyConfig,
) -> AnomalyResult:
    """Pure scoring of one reading against the household's history. No database access."""
    features = compute_features(history, reading_m3, reading_date, config)
    rule = apply_rules(features, config)

    score: Optional[float] = None
    model_used = False
    if rule is not None:
        anomaly_type = rule
        score = 0.0 if rule == AnomalyType.BASELINE else 1.0
    elif is_cold_start(features, config) or model is None:
        anomaly_type = AnomalyType.NORMAL
        score = 0.0
    else:
        score, flagged = model.score(features.model_vector())
        model_used = True
        anomaly_type = classify_model_anomaly(features, config) if flagged else AnomalyType.NORMAL

    is_anomaly = anomaly_type not in (AnomalyType.NORMAL, AnomalyType.BASELINE)
    feature_dict = features.to_dict() if features else {}
    feature_dict["cold_start"] = features is None or is_cold_start(features, config)
    return AnomalyResult(
        household_id=household_id,
        reading_m3=reading_m3,
        daily_consumption=round(features.daily_consumption, 6) if features else None,
        anomaly_score=score,
        is_anomaly=is_anomaly,
        anomaly_type=anomaly_type.value,
        needs_retake=False,
        message_for_household=message_for(anomaly_type),
        features=feature_dict,
        model_used=model_used,
        pending_review=anomaly_type in PENDING_REVIEW_TYPES,
    )


def load_history(
    db: Session, household_id: str, before: datetime, exclude_reading_id: Optional[int] = None
) -> List[ReadingPoint]:
    """Confirmed previous readings for this meter. Pending and rejected readings are never history."""
    query = db.query(Reading.submitted_value, Reading.submission_time).filter(
        Reading.meter_id == household_id,
        Reading.submission_time < before,
        Reading.validation_status.notin_(NOT_CONFIRMED),
    )
    if exclude_reading_id is not None:
        query = query.filter(Reading.reading_id != exclude_reading_id)
    points = [ReadingPoint(date=t, reading_m3=v) for v, t in query.order_by(Reading.submission_time).all()]
    return since_last_reset(points)


def since_last_reset(points: List[ReadingPoint]) -> List[ReadingPoint]:
    """Meters only count up, so a drop in confirmed readings is a fresh start: a replaced meter,
    a staff correction (app/services/meter_correction.py) or an accepted lower reading. History
    begins there; earlier readings describe the old count and would look like negative use."""
    start = 0
    for i in range(1, len(points)):
        if points[i].reading_m3 < points[i - 1].reading_m3:
            start = i
    return points[start:]


def _save_flag(
    db: Session, result: AnomalyResult, reading_id: Optional[int], staff_review: Optional[bool] = None
) -> None:
    flag = AnomalyFlag(
        household_id=result.household_id,
        reading_id=reading_id,
        anomaly_type=result.anomaly_type,
        anomaly_score=result.anomaly_score,
        features=result.features,
        requires_staff_review=(
            action_for(AnomalyType(result.anomaly_type)).staff_review if staff_review is None else staff_review
        ),
        message_for_household=result.message_for_household,
        status=FLAG_STATUS_OPEN,
    )
    db.add(flag)
    db.flush()
    result.flag_id = flag.id


def _resolve(config: Optional[AnomalyConfig], model: Optional[AnomalyModel]):
    config = config or AnomalyConfig.from_env()
    return config, (model if model is not None else load_model_if_available(config))


def score_reading(
    db: Session,
    household_id: str,
    reading_m3: float,
    reading_date: datetime,
    reading_id: Optional[int] = None,
    config: Optional[AnomalyConfig] = None,
    model: Optional[AnomalyModel] = None,
) -> AnomalyResult:
    """Score an already-converted reading. Flags are flushed, not committed; the caller commits."""
    config, model = _resolve(config, model)
    history = load_history(db, household_id, reading_date, exclude_reading_id=reading_id)
    result = assess(household_id, history, reading_m3, reading_date, model, config)
    if result.is_anomaly:
        _save_flag(db, result, reading_id)
    return result


def score_submission(
    db: Session,
    household_id: str,
    reading_digits: str,
    reading_date: datetime,
    config: Optional[AnomalyConfig] = None,
    model: Optional[AnomalyModel] = None,
) -> AnomalyResult:
    """Score raw CRNN digits. Wrong-length or non-digit input returns a retake result, never a guess."""
    if db.query(Meter.meter_id).filter(Meter.meter_id == household_id).first() is None:
        raise LookupError(f"Household/meter '{household_id}' not found")

    config, model = _resolve(config, model)
    conversion = digits_to_m3(reading_digits, config)
    if not conversion.ok:
        result = AnomalyResult(
            household_id=household_id,
            reading_m3=None,
            daily_consumption=None,
            anomaly_score=None,
            is_anomaly=True,
            anomaly_type=AnomalyType.MISREAD_SUSPECTED.value,
            needs_retake=True,
            message_for_household=RETAKE_MESSAGE,
            features={"conversion_error": conversion.reason, "reading_digits": reading_digits},
        )
        _save_flag(db, result, reading_id=None, staff_review=False)  # nothing for staff to decide
        return result

    return score_reading(db, household_id, conversion.reading_m3, reading_date, config=config, model=model)


@dataclass
class Submission:
    reading: Reading
    anomaly: AnomalyResult
    consumption_m3: float
    bill: Optional[Bill] = None


def has_baseline(db: Session, meter: Meter) -> bool:
    """Is there a starting value to measure a new reading from? A confirmed reading (a staff
    correction or first reading counts), or a stored last_reading (imported meters). A meter
    added without a first reading has neither: meters.last_reading is 0 and no reading is confirmed."""
    if meter.last_reading:
        return True
    return db.query(Reading.reading_id).filter(
        Reading.meter_id == meter.meter_id,
        Reading.validation_status.notin_(NOT_CONFIRMED),
    ).first() is not None


@dataclass
class Evaluation:
    """What a reading would lead to, worked out without writing anything (evaluate_reading).

    scored     the rules/model result, after the "below the last confirmed reading" check; saved
               as a flag when it is an anomaly
    anomaly    the final result: scored, or a LOCATION_CHECK hold on top of it (a second flag)
    """
    refusal: Optional[ReadingRefused] = None
    consumption_m3: float = 0.0
    scored: Optional[AnomalyResult] = None
    anomaly: Optional[AnomalyResult] = None
    location: Optional[LocationCheck] = None


def evaluate_reading(
    db: Session,
    meter: Meter,
    reading_m3: float,
    now: datetime,
    evidence: Optional[PhotoEvidence] = None,
    household: bool = False,
    config: Optional[AnomalyConfig] = None,
    model: Optional[AnomalyModel] = None,
) -> Evaluation:
    """Every check a new reading goes through, read-only: nothing is added to or changed in the session.

    submit_reading calls it with the meter locked and then stores the outcome. A refusal (the
    household must wait, or the same value was just sent) is returned, not raised.
    """
    if household:
        block = reading_block(db, meter, now)
        if block:
            return Evaluation(refusal=ReadingRefused(block.message, block))
    duplicate = (
        db.query(Reading.reading_id)
        .filter(
            Reading.meter_id == meter.meter_id,
            Reading.submitted_value == reading_m3,
            Reading.submission_time > now - DUPLICATE_WINDOW,
            Reading.validation_status != READING_REJECTED,
        )
        .first()
    )
    if duplicate:
        return Evaluation(refusal=ReadingRefused(
            "This reading was just sent. Check your bills and messages before sending it again."
        ))

    config, model = _resolve(config, model)
    consumption = reading_m3 - meter.last_reading
    history = load_history(db, meter.meter_id, now)
    scored = assess(meter.meter_id, history, reading_m3, now, model, config)
    if not has_baseline(db, meter):
        # Nothing to measure this reading from: billing it would charge the whole register.
        scored = AnomalyResult(
            household_id=meter.meter_id,
            reading_m3=reading_m3,
            daily_consumption=None,
            anomaly_score=0.0,
            is_anomaly=True,
            anomaly_type=AnomalyType.NO_BASELINE.value,
            needs_retake=False,
            message_for_household=message_for(AnomalyType.NO_BASELINE),
            features={"no_baseline": True},
            pending_review=True,
        )
    elif consumption < 0 and scored.anomaly_type != AnomalyType.MISREAD_SUSPECTED.value:
        # The meter's confirmed reading is higher, even if no reading rows explain it (e.g. imported meters).
        scored = AnomalyResult(
            household_id=meter.meter_id,
            reading_m3=reading_m3,
            daily_consumption=None,
            anomaly_score=1.0,
            is_anomaly=True,
            anomaly_type=AnomalyType.MISREAD_SUSPECTED.value,
            needs_retake=False,
            message_for_household=message_for(AnomalyType.MISREAD_SUSPECTED),
            features={"below_last_confirmed_m3": meter.last_reading},
            pending_review=True,
        )

    evaluation = Evaluation(consumption_m3=consumption, scored=scored, anomaly=scored)
    if evidence is not None:
        evaluation.location = check_location(meter.gps_lat, meter.gps_lng, evidence)
        evaluation.anomaly = _location_hold(meter, scored, evaluation.location, evidence)
    return evaluation


def _location_hold(
    meter: Meter, scored: AnomalyResult, check: LocationCheck, evidence: PhotoEvidence
) -> AnomalyResult:
    """Hold the reading if where the photo was taken needs an officer's look."""
    if not check.needs_review:
        return scored
    extra = check.features(evidence)
    if scored.pending_review:
        # Already held for another reason: add the location to what the officer sees.
        scored.features = {**(scored.features or {}), **extra}
        return scored
    return AnomalyResult(
        household_id=meter.meter_id,
        reading_m3=scored.reading_m3,
        daily_consumption=scored.daily_consumption,
        anomaly_score=scored.anomaly_score,
        is_anomaly=True,
        anomaly_type=AnomalyType.LOCATION_CHECK.value,
        needs_retake=False,
        message_for_household=message_for(AnomalyType.LOCATION_CHECK),
        features={**(scored.features or {}), **extra},
        model_used=scored.model_used,
        pending_review=True,
    )


def submit_reading(
    db: Session,
    meter: Meter,
    customer_id: Optional[str],
    reading_m3: float,
    method: str,
    evidence: Optional[PhotoEvidence] = None,
    household: bool = False,
) -> Submission:
    """Store a household reading, score it, and either confirm and bill it or hold it for staff review.

    The meter is locked first, then evaluate_reading runs every check: a household (household=True)
    must be allowed to send a reading now (app/services/reading_window.py), and nobody may send the
    same value twice within DUPLICATE_WINDOW. Either raises ReadingRefused with nothing stored.

    Held readings (MISREAD_SUSPECTED, SPIKE, anything below the last confirmed reading, or a photo
    whose location or source needs checking, see app/anomaly/location.py) are not billed and do not move
    meters.last_reading. Commits; call notify_household afterwards.
    """
    now = datetime.utcnow()
    meter = lock_meter(db, meter.meter_id)
    evaluation = evaluate_reading(db, meter, reading_m3, now, evidence=evidence, household=household)
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
        _save_flag(db, scored, reading.reading_id)
    if anomaly is not scored:
        _save_flag(db, anomaly, reading.reading_id)
    check = evaluation.location
    if check is not None:
        db.add(ReadingEvidence(
            reading_id=reading.reading_id, photo_source=evidence.photo_source, lat=evidence.lat, lng=evidence.lng,
            accuracy_m=evidence.accuracy_m, distance_m=check.distance_m, outcome=check.outcome,
        ))

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
