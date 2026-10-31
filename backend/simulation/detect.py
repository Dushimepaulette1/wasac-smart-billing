"""Phase 3: score the simulated months with the app's rules and an unsupervised Isolation Forest.

The detector never sees a label. observations_from_ledger copies named, label-free fields out of the
ledger, and everything after it works from those copies, so ground_truth_anomaly and anomaly_type
cannot reach the features, the training matrix or the fit. Only Phase 4 joins detections to labels.

    features    the app's three MODEL_FEATURES, plus volumetric_deviation
    baseline    the mean of a customer's first 3 Active months, then frozen, so a long leak cannot
                raise its own baseline. Faults only start after these months.
    scored      Active months after the baseline. Disconnected and reconnection months have zero
                use that billing already explains, so they are left out.
    time        each Active month counts as one 30-day period, skipping closed months: otherwise
                the month after a disconnection would look like half its real use.
    training    train customers only, leaving out months a rule already catches, as the app's
                build_training_matrix does. Faults a rule misses stay in, as they would in real data.

consecutive_unpaid_months is left out on purpose: one unpaid bill disconnects a customer at once, so
it is always 0 in the Active months being scored and carries no information.

The model is kept in memory. Nothing here calls AnomalyModel.save, so the app stays rules only.
"""
import csv
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timedelta
from pathlib import Path
from statistics import mean
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

from app.anomaly.config import AnomalyConfig
from app.anomaly.features import EPS_DAILY_M3, MODEL_FEATURES, ReadingPoint, compute_features
from app.anomaly.model import AnomalyModel
from app.anomaly.rules import apply_rules
from simulation.generate import Customer
from simulation.ledger import LedgerRow, Simulation, State

BASELINE_MONTHS = 3
FEATURE_COLUMNS = (*MODEL_FEATURES, "volumetric_deviation")
TEST_SHARE = 0.3
DAYS_PER_PERIOD = 30
AXIS_START = datetime(2024, 1, 1)
SPLIT_STREAM = 1  # keeps the split independent of the data generator's four streams


@dataclass(frozen=True)
class MonthObservation:
    """All the detector may know about a month: what a meter and the account state would show."""

    customer_id: str
    month: int
    state: str
    opening_reading_m3: float
    closing_reading_m3: float
    volume_m3: float


@dataclass(frozen=True)
class MonthFeatures:
    customer_id: str
    month: int
    vector: Tuple[float, ...]  # in FEATURE_COLUMNS order
    volumetric_deviation: float
    rule_type: Optional[str]  # what apply_rules said; None if no rule fired


@dataclass(frozen=True)
class Detection:
    customer_id: str
    month: int
    volumetric_deviation: float
    anomaly_score: float  # higher is more anomalous
    forest_flag: bool
    rule_flag: bool
    rule_type: str


@dataclass(frozen=True)
class DetectionResult:
    model: AnomalyModel
    train_customers: List[str]
    test_customers: List[str]
    detections: List[Detection]  # test customers only


def observations_from_ledger(ledger: Iterable[LedgerRow]) -> Dict[str, List[MonthObservation]]:
    """Each customer's months in order, with only the label-free fields."""
    observations: Dict[str, List[MonthObservation]] = {}
    for row in ledger:
        observations.setdefault(row.customer_id, []).append(MonthObservation(
            customer_id=row.customer_id,
            month=row.month,
            state=row.state,
            opening_reading_m3=row.opening_reading_m3,
            closing_reading_m3=row.closing_reading_m3,
            volume_m3=row.volume_m3,
        ))
    for months in observations.values():
        months.sort(key=lambda o: o.month)
    return observations


def volumetric_deviation(volume_m3: float, baseline_m3: float) -> float:
    """(Current volume - baseline) / baseline. The floor keeps it finite for a near-zero baseline."""
    baseline = max(baseline_m3, EPS_DAILY_M3)
    return (volume_m3 - baseline) / baseline


def _period_end(period: int) -> datetime:
    return AXIS_START + timedelta(days=period * DAYS_PER_PERIOD)


def customer_features(months: Sequence[MonthObservation], config: AnomalyConfig) -> List[MonthFeatures]:
    """One row per Active month after the baseline; none if the customer has no such month."""
    active = [m for m in months if m.state == State.ACTIVE.value]
    if len(active) <= BASELINE_MONTHS:
        return []
    baseline = mean(m.volume_m3 for m in active[:BASELINE_MONTHS])
    points = [ReadingPoint(_period_end(0), active[0].opening_reading_m3)]
    points += [ReadingPoint(_period_end(i), m.closing_reading_m3) for i, m in enumerate(active, start=1)]

    rows = []
    for index in range(BASELINE_MONTHS, len(active)):
        current = points[index + 1]
        features = compute_features(points[: index + 1], current.reading_m3, current.date, config)
        month = active[index]
        deviation = volumetric_deviation(month.volume_m3, baseline)
        rule = apply_rules(features, config)
        rows.append(MonthFeatures(
            customer_id=month.customer_id,
            month=month.month,
            vector=(*features.model_vector(), deviation),
            volumetric_deviation=deviation,
            rule_type=rule.value if rule else None,
        ))
    return rows


def split_customers(customers: Sequence[Customer], seed: int, test_share: float = TEST_SHARE) -> Tuple[List[str], List[str]]:
    """Whole customers go to one side, with each customer type split in the same proportion."""
    rng = np.random.default_rng([seed, SPLIT_STREAM])
    train: List[str] = []
    test: List[str] = []
    for customer_type in sorted({c.customer_type for c in customers}):
        ids = [c.customer_id for c in customers if c.customer_type == customer_type]
        rng.shuffle(ids)
        n_test = round(len(ids) * test_share)
        test += ids[:n_test]
        train += ids[n_test:]
    return sorted(train), sorted(test)


def feature_matrix(rows: Sequence[MonthFeatures]) -> np.ndarray:
    return np.asarray([row.vector for row in rows], dtype=float).reshape(-1, len(FEATURE_COLUMNS))


def train_forest(rows: Sequence[MonthFeatures], config: AnomalyConfig) -> AnomalyModel:
    """Fit on the months no rule caught, like the app's build_training_matrix."""
    return AnomalyModel.train(feature_matrix([r for r in rows if r.rule_type is None]), config)


def score_months(model: AnomalyModel, rows: Sequence[MonthFeatures]) -> List[Detection]:
    """The same calculation as AnomalyModel.score, on all rows at once."""
    if not rows:
        return []
    X = feature_matrix(rows)
    scores = -model.estimator.score_samples(X)
    flags = model.estimator.predict(X) == -1
    return [
        Detection(
            customer_id=row.customer_id,
            month=row.month,
            volumetric_deviation=round(row.volumetric_deviation, 6),
            anomaly_score=round(float(score), 4),
            forest_flag=bool(flag),
            rule_flag=row.rule_type is not None,
            rule_type=row.rule_type or "none",
        )
        for row, score, flag in zip(rows, scores, flags)
    ]


def run_detection(simulation: Simulation, config: Optional[AnomalyConfig] = None) -> DetectionResult:
    """Train on the train customers and score the test customers.

    AnomalyConfig() rather than from_env: results must not change with this machine's settings.
    """
    config = config or AnomalyConfig()
    observations = observations_from_ledger(simulation.ledger)
    train_ids, test_ids = split_customers(simulation.customers, simulation.config.seed)
    train_rows = [row for cid in train_ids for row in customer_features(observations[cid], config)]
    test_rows = [row for cid in test_ids for row in customer_features(observations[cid], config)]
    model = train_forest(train_rows, config)
    return DetectionResult(model, train_ids, test_ids, score_months(model, test_rows))


def write_detections(detections: Iterable[Detection], output_dir: Path) -> Path:
    """detections.csv, without labels: Phase 4 joins them from ledger.csv."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "detections.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=[f.name for f in fields(Detection)], lineterminator="\n")
        writer.writeheader()
        writer.writerows(asdict(d) for d in detections)
    return path
