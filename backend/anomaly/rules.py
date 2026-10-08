import math
from enum import Enum
from typing import Optional

from anomaly.config import AnomalyConfig
from anomaly.features import SubmissionFeatures


class AnomalyType(str, Enum):
    NORMAL = "NORMAL"
    BASELINE = "BASELINE"
    MISREAD_SUSPECTED = "MISREAD_SUSPECTED"
    SPIKE = "SPIKE"
    SUSTAINED_HIGH = "SUSTAINED_HIGH"
    METER_STUCK = "METER_STUCK"
    UNUSUAL = "UNUSUAL"


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
    return None


def is_cold_start(features: SubmissionFeatures, config: AnomalyConfig) -> bool:
    return features.n_history < config.min_history_periods


def looks_like_digit_shift(ratio: float, config: AnomalyConfig) -> bool:
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
