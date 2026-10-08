import math
from dataclasses import asdict, dataclass
from datetime import datetime
from statistics import mean, median
from typing import List, Optional, Sequence

from anomaly.config import AnomalyConfig

# 10 litres/day: keeps ratios finite for households whose normal use is ~0.
EPS_DAILY_M3 = 0.01
ZERO_CONSUMPTION_M3 = 0.0005
MAD_TO_SIGMA = 1.4826

# Order matters: the saved IsolationForest expects exactly this column order.
MODEL_FEATURES = ("log_ratio_to_median", "signed_log_robust_z", "log_ratio_to_recent")


@dataclass(frozen=True)
class ReadingPoint:
    date: datetime
    reading_m3: float


@dataclass(frozen=True)
class Period:
    days: float
    consumption_m3: float
    daily_consumption: float


@dataclass(frozen=True)
class SubmissionFeatures:
    previous_reading_m3: float
    days_since_last: float
    consumption_m3: float
    daily_consumption: float
    n_history: int
    history_median_daily: Optional[float]
    ratio_to_median: float
    robust_z: float
    ratio_to_recent: float
    recent_ratios: List[float]
    zero_streak_days: float

    def model_vector(self) -> List[float]:
        return [
            math.log(self.ratio_to_median),
            math.copysign(math.log1p(abs(self.robust_z)), self.robust_z),
            math.log(self.ratio_to_recent),
        ]

    def to_dict(self) -> dict:
        d = asdict(self)
        d.update(zip(MODEL_FEATURES, self.model_vector()))
        return {k: (round(v, 6) if isinstance(v, float) else v) for k, v in d.items()}


def _days_between(start: datetime, end: datetime) -> float:
    return max(1.0, (end - start).total_seconds() / 86400.0)


def _ratio(value: float, reference: float) -> float:
    return (max(value, 0.0) + EPS_DAILY_M3) / (max(reference, 0.0) + EPS_DAILY_M3)


def build_periods(points: Sequence[ReadingPoint]) -> List[Period]:
    ordered = sorted(points, key=lambda p: p.date)
    periods = []
    for prev, cur in zip(ordered, ordered[1:]):
        days = _days_between(prev.date, cur.date)
        consumption = cur.reading_m3 - prev.reading_m3
        periods.append(Period(days=days, consumption_m3=consumption, daily_consumption=consumption / days))
    return periods


def compute_features(
    history: Sequence[ReadingPoint],
    reading_m3: float,
    reading_date: datetime,
    config: AnomalyConfig,
) -> Optional[SubmissionFeatures]:
    """Describe a new reading relative to this household's own previous readings.

    Returns None when there is no previous reading (baseline submission).
    """
    ordered = sorted(history, key=lambda p: p.date)
    if not ordered:
        return None

    previous = ordered[-1]
    days = _days_between(previous.date, reading_date)
    consumption = reading_m3 - previous.reading_m3
    daily = consumption / days

    past = build_periods(ordered)
    past_daily = [p.daily_consumption for p in past]

    if past_daily:
        hist_median = median(past_daily)
        mad = median(abs(x - hist_median) for x in past_daily)
        scale = max(MAD_TO_SIGMA * mad, 0.1 * abs(hist_median), 0.05)
        robust_z = (daily - hist_median) / scale
        ratio_to_median = _ratio(daily, hist_median)
        ratio_to_recent = _ratio(daily, mean(past_daily[-3:]))
        window = past_daily[-(config.sustained_periods - 1):] if config.sustained_periods > 1 else []
        recent_ratios = [_ratio(x, hist_median) for x in window] + [ratio_to_median]
    else:
        hist_median = None
        robust_z = 0.0
        ratio_to_median = 1.0
        ratio_to_recent = 1.0
        recent_ratios = [1.0]

    zero_streak = 0.0
    if abs(consumption) < ZERO_CONSUMPTION_M3:
        zero_streak = days
        for p in reversed(past):
            if abs(p.consumption_m3) >= ZERO_CONSUMPTION_M3:
                break
            zero_streak += p.days

    return SubmissionFeatures(
        previous_reading_m3=previous.reading_m3,
        days_since_last=days,
        consumption_m3=consumption,
        daily_consumption=daily,
        n_history=len(past),
        history_median_daily=hist_median,
        ratio_to_median=ratio_to_median,
        robust_z=robust_z,
        ratio_to_recent=ratio_to_recent,
        recent_ratios=recent_ratios,
        zero_streak_days=zero_streak,
    )
