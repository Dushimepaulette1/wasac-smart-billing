from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import List, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from anomaly.config import AnomalyConfig
from anomaly.db_models import FLAG_STATUS_OPEN, AnomalyFlag
from anomaly.features import ReadingPoint, compute_features
from anomaly.model import AnomalyModel, load_model_if_available
from anomaly.notifications import action_for, dispatch, message_for
from anomaly.readings import digits_to_m3
from anomaly.rules import AnomalyType, apply_rules, classify_model_anomaly, is_cold_start
from database import Customer, Meter, Reading


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
        needs_retake=anomaly_type == AnomalyType.MISREAD_SUSPECTED,
        message_for_household=message_for(anomaly_type),
        features=feature_dict,
        model_used=model_used,
    )


def load_history(
    db: Session, household_id: str, before: datetime, exclude_reading_id: Optional[int] = None
) -> List[ReadingPoint]:
    """Previous readings for this meter, excluding ones still flagged as suspected misreads."""
    untrusted = select(AnomalyFlag.reading_id).where(
        AnomalyFlag.household_id == household_id,
        AnomalyFlag.anomaly_type == AnomalyType.MISREAD_SUSPECTED.value,
        AnomalyFlag.status == FLAG_STATUS_OPEN,
        AnomalyFlag.reading_id.isnot(None),
    )
    query = db.query(Reading.submitted_value, Reading.submission_time).filter(
        Reading.meter_id == household_id,
        Reading.submission_time < before,
        Reading.reading_id.notin_(untrusted),
    )
    if exclude_reading_id is not None:
        query = query.filter(Reading.reading_id != exclude_reading_id)
    return [ReadingPoint(date=t, reading_m3=v) for v, t in query.order_by(Reading.submission_time).all()]


def _save_flag(db: Session, result: AnomalyResult, reading_id: Optional[int]) -> None:
    flag = AnomalyFlag(
        household_id=result.household_id,
        reading_id=reading_id,
        anomaly_type=result.anomaly_type,
        anomaly_score=result.anomaly_score,
        features=result.features,
        requires_staff_review=action_for(AnomalyType(result.anomaly_type)).staff_review,
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
            message_for_household=message_for(AnomalyType.MISREAD_SUSPECTED),
            features={"conversion_error": conversion.reason, "reading_digits": reading_digits},
        )
        _save_flag(db, result, reading_id=None)
        return result

    return score_reading(db, household_id, conversion.reading_m3, reading_date, config=config, model=model)


def notify_household(db: Session, result: AnomalyResult) -> List[str]:
    """Send the notifications for a flagged result. Call after the transaction commits."""
    if not result.is_anomaly:
        return []
    phone = (
        db.query(Customer.phone).filter(Customer.meter_id == result.household_id).scalar()
    )
    return dispatch(AnomalyType(result.anomaly_type), phone, result.message_for_household)
