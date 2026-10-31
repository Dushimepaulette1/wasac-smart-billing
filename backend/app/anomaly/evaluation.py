"""Every check a new reading goes through, read-only: POST /check-reading shows the answer to the
household, and submit_reading (app/anomaly/service.py) stores it."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.anomaly.config import AnomalyConfig
from app.anomaly.edits import EditCheck, check_edit
from app.anomaly.location import LocationCheck, PhotoEvidence, check_location
from app.anomaly.model import AnomalyModel
from app.anomaly.notifications import message_for
from app.anomaly.readings import rollover_consumption
from app.anomaly.rules import AnomalyType
from app.anomaly.scoring import AnomalyResult, assess, load_history, resolve_detector
from app.anomaly.statuses import NOT_CONFIRMED, READING_REJECTED
from app.models import Meter, PhotoRead, Reading
from app.services.reading_window import ReadingBlock, reading_block

# The same value for the same meter again within this time is a retry or a double tap, not a reading.
DUPLICATE_WINDOW = timedelta(minutes=2)


class ReadingRefused(Exception):
    """The reading was not stored: the household must wait (block), or it was just sent (duplicate)."""

    def __init__(self, message: str, block: Optional[ReadingBlock] = None):
        super().__init__(message)
        self.message = message
        self.block = block


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

    scored     the rules/model result, after the no-starting-value and "below the last confirmed
               reading" checks; saved as a flag when it is an anomaly
    anomaly    the final result: scored, or an EDITED_DOWN / LOCATION_CHECK hold on top of it (a
               second flag)
    edit       how the household's value compares with the photo reader's (app/anomaly/edits.py)
    """
    refusal: Optional[ReadingRefused] = None
    consumption_m3: float = 0.0
    scored: Optional[AnomalyResult] = None
    anomaly: Optional[AnomalyResult] = None
    location: Optional[LocationCheck] = None
    edit: Optional[EditCheck] = None


def evaluate_reading(
    db: Session,
    meter: Meter,
    reading_m3: float,
    now: datetime,
    evidence: Optional[PhotoEvidence] = None,
    household: bool = False,
    config: Optional[AnomalyConfig] = None,
    model: Optional[AnomalyModel] = None,
    photo: Optional[PhotoRead] = None,
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

    config, model = resolve_detector(config, model)
    consumption = round(reading_m3 - meter.last_reading, 3)
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
    elif rollover_consumption(meter.last_reading, reading_m3) is not None:
        consumption = rollover_consumption(meter.last_reading, reading_m3)
        scored = AnomalyResult(
            household_id=meter.meter_id,
            reading_m3=reading_m3,
            daily_consumption=None,
            anomaly_score=1.0,
            is_anomaly=True,
            anomaly_type=AnomalyType.ROLLOVER.value,
            needs_retake=False,
            message_for_household=message_for(AnomalyType.ROLLOVER),
            features={"rollover": True, "previous_reading_m3": meter.last_reading, "consumption_m3": consumption},
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
    if photo is not None:
        evaluation.edit = check_edit(photo.reader_digits, photo.guidance, reading_m3, config)
        evaluation.anomaly = _edit_hold(meter, scored, evaluation.edit)
    if evidence is not None:
        evaluation.location = check_location(meter.gps_lat, meter.gps_lng, evidence)
        evaluation.anomaly = _location_hold(meter, evaluation.anomaly, evaluation.location, evidence)
    return evaluation


# Why a reading waits for an officer, in one word the household app translates (POST /check-reading).
REVIEW_REASONS = {
    AnomalyType.NO_BASELINE: "first_reading",
    AnomalyType.SPIKE: "high_use",
    AnomalyType.EDITED_DOWN: "edited_down",
    AnomalyType.LOCATION_CHECK: "location",
    AnomalyType.ROLLOVER: "rollover",
}


def review_reason(evaluation: Evaluation) -> Optional[str]:
    """The household-facing reason a reading would be held, or None if it would be billed."""
    anomaly = evaluation.anomaly
    if anomaly is None or not anomaly.pending_review:
        return None
    kind = AnomalyType(anomaly.anomaly_type)
    if kind == AnomalyType.MISREAD_SUSPECTED:
        return "below_previous" if evaluation.consumption_m3 < 0 else "misread"
    return REVIEW_REASONS.get(kind, "misread")


def _edit_hold(meter: Meter, scored: AnomalyResult, edit: EditCheck) -> AnomalyResult:
    """Record the AI read and the household's value for the officer; hold the reading if the
    household lowered a reliable read by edit_hold_m3 or more and nothing else holds it already."""
    scored.features = {**(scored.features or {}), **edit.features()}
    if not edit.hold or scored.pending_review:
        return scored
    return AnomalyResult(
        household_id=meter.meter_id,
        reading_m3=scored.reading_m3,
        daily_consumption=scored.daily_consumption,
        anomaly_score=scored.anomaly_score,
        is_anomaly=True,
        anomaly_type=AnomalyType.EDITED_DOWN.value,
        needs_retake=False,
        message_for_household=message_for(AnomalyType.EDITED_DOWN),
        features=dict(scored.features),
        model_used=scored.model_used,
        pending_review=True,
    )


def _location_hold(
    meter: Meter, scored: AnomalyResult, check: LocationCheck, evidence: PhotoEvidence
) -> AnomalyResult:  # scored: the result so far (may already be an EDITED_DOWN hold)
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
