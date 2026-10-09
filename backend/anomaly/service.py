from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import List, Optional, Sequence

from sqlalchemy.orm import Session

from anomaly.config import AnomalyConfig
from anomaly.db_models import FLAG_STATUS_OPEN, AnomalyFlag
from anomaly.features import ReadingPoint, compute_features
from anomaly.model import AnomalyModel, load_model_if_available
from anomaly.notifications import RETAKE_MESSAGE, action_for, dispatch, message_for, send_sms
from anomaly.readings import digits_to_m3
from anomaly.rules import AnomalyType, apply_rules, classify_model_anomaly, is_cold_start
from anomaly.statuses import (
    NOT_CONFIRMED,
    PENDING_REVIEW_TYPES,
    READING_FLAGGED,
    READING_PENDING,
    READING_VALID,
)
from database import Bill, Customer, Meter, Reading, build_bill


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
    return [ReadingPoint(date=t, reading_m3=v) for v, t in query.order_by(Reading.submission_time).all()]


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


def submit_reading(
    db: Session, meter: Meter, customer_id: Optional[str], reading_m3: float, method: str
) -> Submission:
    """Store a household reading, score it, and either confirm and bill it or hold it for staff review.

    Held readings (MISREAD_SUSPECTED, SPIKE, or anything below the last confirmed reading) are not
    billed and do not move meters.last_reading. Commits; call notify_household afterwards.
    """
    now = datetime.utcnow()
    consumption = reading_m3 - meter.last_reading
    reading = Reading(
        meter_id=meter.meter_id,
        submitted_value=reading_m3,
        implied_consumption=consumption,
        submission_method=method,
        submission_time=now,
    )
    db.add(reading)
    db.flush()

    anomaly = score_reading(db, meter.meter_id, reading_m3, now, reading_id=reading.reading_id)
    if consumption < 0 and anomaly.anomaly_type != AnomalyType.MISREAD_SUSPECTED.value:
        # The meter's confirmed reading is higher, even if no reading rows explain it (e.g. imported meters).
        if anomaly.flag_id:
            db.delete(db.get(AnomalyFlag, anomaly.flag_id))
        anomaly = AnomalyResult(
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
        _save_flag(db, anomaly, reading.reading_id)

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
        send_sms(phone, result.message_for_household)
        return ["sms_household_logged"]
    return dispatch(AnomalyType(result.anomaly_type), phone, result.message_for_household)
