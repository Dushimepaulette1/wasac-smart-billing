import os
from dataclasses import dataclass, field
from pathlib import Path

_DEFAULT_MODEL_PATH = Path(__file__).resolve().parent / "artifacts" / "isolation_forest.joblib"


def _env(name: str, default, cast):
    raw = os.getenv(name)
    return default if raw is None or raw == "" else cast(raw)


@dataclass(frozen=True)
class AnomalyConfig:
    reading_length: int = 8
    decimal_digits: int = 3
    max_daily_m3: float = 5.0
    stuck_days: float = 30.0
    min_history_periods: int = 3
    contamination: float = 0.05
    random_state: int = 42
    n_estimators: int = 200
    spike_ratio: float = 3.0
    sustained_ratio: float = 1.5
    sustained_periods: int = 3
    # A ratio within this log10 distance of 10x or 100x looks like a shifted digit.
    misread_log10_tolerance: float = 0.15
    model_path: Path = field(default=_DEFAULT_MODEL_PATH)

    @classmethod
    def from_env(cls) -> "AnomalyConfig":
        d = cls()
        return cls(
            reading_length=_env("ANOMALY_READING_LENGTH", d.reading_length, int),
            decimal_digits=_env("ANOMALY_DECIMAL_DIGITS", d.decimal_digits, int),
            max_daily_m3=_env("ANOMALY_MAX_DAILY_M3", d.max_daily_m3, float),
            stuck_days=_env("ANOMALY_STUCK_DAYS", d.stuck_days, float),
            min_history_periods=_env("ANOMALY_MIN_HISTORY_PERIODS", d.min_history_periods, int),
            contamination=_env("ANOMALY_CONTAMINATION", d.contamination, float),
            random_state=_env("ANOMALY_RANDOM_STATE", d.random_state, int),
            n_estimators=_env("ANOMALY_N_ESTIMATORS", d.n_estimators, int),
            spike_ratio=_env("ANOMALY_SPIKE_RATIO", d.spike_ratio, float),
            sustained_ratio=_env("ANOMALY_SUSTAINED_RATIO", d.sustained_ratio, float),
            sustained_periods=_env("ANOMALY_SUSTAINED_PERIODS", d.sustained_periods, int),
            misread_log10_tolerance=_env(
                "ANOMALY_MISREAD_LOG10_TOLERANCE", d.misread_log10_tolerance, float
            ),
            model_path=_env("ANOMALY_MODEL_PATH", d.model_path, Path),
        )
