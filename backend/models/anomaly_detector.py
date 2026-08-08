import math
from typing import List, Tuple


class AnomalyDetector:
    """
    Stage 3: Statistical anomaly detection for consumption validation.
    Production version uses Isolation Forest (scikit-learn).

    Current stub: 2-sigma Z-score check on historical consumption list.
    """

    SIGMA_THRESHOLD = 2.0

    def check(self, consumption: float, history: List[float]) -> Tuple[bool, float]:
        """
        Returns (is_anomalous, anomaly_score).
        anomaly_score: float in [0, 1] — higher means more anomalous.
        """
        if not history or len(history) < 2:
            return False, 0.1

        mean = sum(history) / len(history)
        variance = sum((x - mean) ** 2 for x in history) / len(history)
        std = math.sqrt(variance) if variance > 0 else 1.0

        z_score = abs(consumption - mean) / std

        # Normalize to [0, 1] score via sigmoid-like mapping
        anomaly_score = min(z_score / (self.SIGMA_THRESHOLD * 3), 1.0)

        if z_score > self.SIGMA_THRESHOLD:
            # Clamp score between 0.5 and 1.0 for anomalous readings
            anomaly_score = max(0.5, min(anomaly_score, 1.0))
            return True, round(anomaly_score, 3)

        anomaly_score = min(anomaly_score, 0.29)
        return False, round(anomaly_score, 3)
