import logging
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional, Sequence, Tuple

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest

from anomaly.config import AnomalyConfig
from anomaly.features import MODEL_FEATURES, ReadingPoint, compute_features
from anomaly.rules import apply_rules

logger = logging.getLogger(__name__)


def build_training_matrix(
    histories: Iterable[Sequence[ReadingPoint]], config: AnomalyConfig
) -> np.ndarray:
    """One row per historical period that has enough prior periods for the model.

    Periods a rule would already catch (backwards, >max/day, stuck) are left out so the
    forest learns what normal looks like.
    """
    rows = []
    for history in histories:
        points = sorted(history, key=lambda p: p.date)
        for j in range(config.min_history_periods + 1, len(points)):
            features = compute_features(points[:j], points[j].reading_m3, points[j].date, config)
            if features is None or apply_rules(features, config) is not None:
                continue
            rows.append(features.model_vector())
    return np.asarray(rows, dtype=float).reshape(-1, len(MODEL_FEATURES))


class AnomalyModel:
    """A single IsolationForest shared by all households; features are household-relative."""

    def __init__(self, estimator: IsolationForest, n_samples: int, trained_at: str):
        self.estimator = estimator
        self.n_samples = n_samples
        self.trained_at = trained_at

    @classmethod
    def train(cls, X: np.ndarray, config: AnomalyConfig) -> "AnomalyModel":
        if len(X) < 10:
            raise ValueError(f"Need at least 10 training periods, got {len(X)}.")
        estimator = IsolationForest(
            n_estimators=config.n_estimators,
            contamination=config.contamination,
            random_state=config.random_state,
        )
        estimator.fit(X)
        return cls(estimator, n_samples=len(X), trained_at=datetime.utcnow().isoformat())

    def save(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "estimator": self.estimator,
                "features": list(MODEL_FEATURES),
                "n_samples": self.n_samples,
                "trained_at": self.trained_at,
            },
            path,
        )
        return path

    @classmethod
    def load(cls, path: Path) -> "AnomalyModel":
        payload = joblib.load(path)
        if tuple(payload["features"]) != MODEL_FEATURES:
            raise ValueError(
                f"Model at {path} was trained on {payload['features']}, expected {list(MODEL_FEATURES)}. Retrain it."
            )
        return cls(payload["estimator"], payload["n_samples"], payload["trained_at"])

    def score(self, vector: Sequence[float]) -> Tuple[float, bool]:
        """Return (anomaly_score in (0, 1], higher = more anomalous; is_anomaly)."""
        X = np.asarray([vector], dtype=float)
        score = float(-self.estimator.score_samples(X)[0])
        is_anomaly = bool(self.estimator.predict(X)[0] == -1)
        return round(score, 4), is_anomaly


_cache: dict = {}


def load_model_if_available(config: AnomalyConfig) -> Optional[AnomalyModel]:
    """Load once per path; None (rules-only mode) if no trained model exists yet."""
    path = Path(config.model_path)
    if path in _cache:
        return _cache[path]
    model = None
    if path.exists():
        model = AnomalyModel.load(path)
    else:
        logger.warning("No anomaly model at %s; running rules only. Train with scripts/train_anomaly_model.py.", path)
    _cache[path] = model
    return model


def clear_model_cache() -> None:
    _cache.clear()
