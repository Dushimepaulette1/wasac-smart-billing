import math
from enum import Enum
from typing import Optional

from app.anomaly.config import AnomalyConfig
from app.anomaly.features import SubmissionFeatures


class AnomalyType(str, Enum):
    NORMAL = "NORMAL"
    BASELINE = "BASELINE"
    MISREAD_SUSPECTED = "MISREAD_SUSPECTED"
    SPIKE = "SPIKE"
    SUSTAINED_HIGH = "SUSTAINED_HIGH"
    METER_STUCK = "METER_STUCK"
    UNUSUAL = "UNUSUAL"
    # Not from the rules or the model: the photo's location or source needs a person to check it
    # (app/anomaly/location.py).
    LOCATION_CHECK = "LOCATION_CHECK"
    # Not from the rules: the meter has no starting value yet (no confirmed reading, last_reading 0),
    # so this reading can only become the starting point. Held; accepting it bills nothing.
    NO_BASELINE = "NO_BASELINE"
    # Not from the rules: the household lowered a reliable AI read by ANOMALY_EDIT_HOLD_M3 or more
    # (app/anomaly/edits.py). Held for an officer; not a judgement that either value is wrong.
    EDITED_DOWN = "EDITED_DOWN"
    # Not from the rules: the register seems to have turned over (app/anomaly/readings.py). Held;
    # accepting it bills the use across the wrap.
    ROLLOVER = "ROLLOVER"


def apply_rules(features: Optional[SubmissionFeatures], config: AnomalyConfig) -> Optional[AnomalyType]:
    """Deterministic checks that always run before the model. None means no rule fired."""
    if features is None:
        return AnomalyType.BASELINE
    if features.consumption_m3 < 0:
        return AnomalyType.MISREAD_SUSPECTED
    if features.daily_consumption > config.max_daily_m3:
        return AnomalyType.SPIKE
    if features.zero_streak_days >= config.stuck_days:
        return AnomalyType.METER_STUCK
    return compare_with_history(features, config)


def has_enough_history(features: SubmissionFeatures, config: AnomalyConfig) -> bool:
    """At least min_history_periods past periods of min_period_days or more, and this reading's own
    period long enough too: only then is its daily use compared with the household's usual."""
    return (features.n_suitable_periods >= config.min_history_periods
            and features.days_since_last >= config.min_period_days)


def compare_with_history(features: SubmissionFeatures, config: AnomalyConfig) -> Optional[AnomalyType]:
    """Daily use far above this household's own median (rules only; the model is not needed).
    About 10x or 100x looks like a shifted digit (a misread), otherwise spike_ratio or more is
    unusually high use. Both are held for an officer. Provisional thresholds (config.py)."""
    if not has_enough_history(features, config):
        return None
    ratio = features.ratio_to_suitable_median
    if looks_like_digit_shift(ratio, config):
        return AnomalyType.MISREAD_SUSPECTED
    if ratio >= config.spike_ratio:
        return AnomalyType.SPIKE
    return None


def is_cold_start(features: SubmissionFeatures, config: AnomalyConfig) -> bool:
    return features.n_history < config.min_history_periods


def looks_like_digit_shift(ratio: float, config: AnomalyConfig) -> bool:
    if ratio <= 0:
        return False
    log_ratio = math.log10(ratio)
    return any(abs(log_ratio - k) <= config.misread_log10_tolerance for k in (1.0, 2.0))


def classify_model_anomaly(features: SubmissionFeatures, config: AnomalyConfig) -> AnomalyType:
    """Name a period the model flagged. Digit-shift is checked first because 10x also exceeds the spike ratio."""
    if looks_like_digit_shift(features.ratio_to_median, config):
        return AnomalyType.MISREAD_SUSPECTED
    if features.ratio_to_median >= config.spike_ratio:
        return AnomalyType.SPIKE
    recent = features.recent_ratios
    if len(recent) >= config.sustained_periods and all(r >= config.sustained_ratio for r in recent):
        return AnomalyType.SUSTAINED_HIGH
    return AnomalyType.UNUSUAL
