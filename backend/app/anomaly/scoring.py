"""Scoring one reading against the household's history: the rules, then the model when there is one.
Pure where it can be (assess); app/anomaly/evaluation.py adds what needs the meter and the photo."""
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import List, Optional, Sequence

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.anomaly.config import AnomalyConfig
from app.anomaly.features import ReadingPoint, compute_features
from app.anomaly.model import AnomalyModel, load_model_if_available
from app.anomaly.notifications import RETAKE_MESSAGE, action_for, message_for
from app.anomaly.readings import digits_to_m3
from app.anomaly.rules import AnomalyType, apply_rules, classify_model_anomaly, has_enough_history, is_cold_start
from app.anomaly.statuses import NOT_CONFIRMED, PENDING_REVIEW_TYPES
from app.models import FLAG_STATUS_OPEN, AnomalyFlag, Meter, Reading


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
    # Not enough suitable history to compare this reading with the household's usual use.
    feature_dict["insufficient_history"] = features is None or not has_enough_history(features, config)
    if anomaly_type == AnomalyType.MISREAD_SUSPECTED and features is not None and features.consumption_m3 >= 0:
        feature_dict["digit_shift"] = True  # about 10x or 100x the usual use, not a lower reading
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
    value = func.coalesce(Reading.corrected_value_m3, Reading.submitted_value)
    query = db.query(value, Reading.submission_time).filter(
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


def save_flag(
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


def resolve_detector(config: Optional[AnomalyConfig], model: Optional[AnomalyModel]):
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
    config, model = resolve_detector(config, model)
    history = load_history(db, household_id, reading_date, exclude_reading_id=reading_id)
    result = assess(household_id, history, reading_m3, reading_date, model, config)
    if result.is_anomaly:
        save_flag(db, result, reading_id)
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

    config, model = resolve_detector(config, model)
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
        save_flag(db, result, reading_id=None, staff_review=False)  # nothing for staff to decide
        return result

    return score_reading(db, household_id, conversion.reading_m3, reading_date, config=config, model=model)
