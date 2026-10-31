"""Detection on the simulation: the frozen baseline, the customer split, and no label leakage."""
import csv
from dataclasses import fields, replace

import numpy as np
import pytest

from app.anomaly.config import AnomalyConfig
from app.anomaly.features import MODEL_FEATURES
from simulation.config import FaultConfig, SimulationConfig
from simulation.detect import (
    BASELINE_MONTHS, FEATURE_COLUMNS, Detection, MonthObservation, customer_features, observations_from_ledger,
    run_detection, score_months, split_customers, train_forest, volumetric_deviation, write_detections,
)
from simulation.ledger import run_simulation

CONFIG = AnomalyConfig()
SMALL = SimulationConfig(n_customers=120)


@pytest.fixture(scope="module")
def simulation():
    return run_simulation(SMALL)


@pytest.fixture(scope="module")
def result(simulation):
    return run_detection(simulation)


def months(volumes, states=None):
    """A customer from a list of monthly volumes; a closed month adds nothing to the meter."""
    rows = []
    reading = 100.0
    for number, volume in enumerate(volumes, start=1):
        state = states[number - 1] if states else "active"
        rows.append(MonthObservation("DEMO-SIM-0001", number, state, reading, reading + volume, volume))
        reading += volume
    return rows


def test_feature_columns_hold_no_labels_and_no_unpaid_count():
    assert FEATURE_COLUMNS == (*MODEL_FEATURES, "volumetric_deviation")
    banned = ("ground_truth", "anomaly_type", "consecutive_unpaid", "bill", "arrears")
    assert not [c for c in FEATURE_COLUMNS if any(word in c for word in banned)]


def test_what_the_detector_receives_has_no_label_fields():
    names = {f.name for f in fields(MonthObservation)}
    assert names.isdisjoint({"ground_truth_anomaly", "anomaly_type", "consecutive_unpaid_months", "water_closed_flag"})


def test_detections_do_not_depend_on_labels(simulation, result):
    """Corrupt every label in the ledger: the result must not move by one digit."""
    corrupted = [
        replace(row, ground_truth_anomaly=1 - row.ground_truth_anomaly, anomaly_type="leak", consecutive_unpaid_months=9)
        for row in simulation.ledger
    ]
    assert run_detection(replace(simulation, ledger=corrupted)).detections == result.detections


def test_volumetric_deviation():
    assert volumetric_deviation(40.0, 10.0) == 3.0
    assert volumetric_deviation(0.0, 10.0) == -1.0
    assert np.isfinite(volumetric_deviation(5.0, 0.0))


def test_baseline_needs_exactly_the_months_before_a_fault_may_start():
    assert BASELINE_MONTHS == FaultConfig().clean_months == CONFIG.min_history_periods


def test_baseline_comes_only_from_the_first_three_active_months():
    rows = customer_features(months([10, 10, 10, 40, 40, 40, 40, 40]), CONFIG)
    assert [r.month for r in rows] == [4, 5, 6, 7, 8]
    assert [r.volumetric_deviation for r in rows] == [3.0] * 5


def test_a_long_leak_stays_visible_in_the_deviation_but_fades_in_the_rolling_ratio():
    rows = customer_features(months([10, 10, 10] + [40] * 9), CONFIG)
    log_ratio = MODEL_FEATURES.index("log_ratio_to_median")
    assert rows[-1].volumetric_deviation == rows[0].volumetric_deviation
    assert rows[-1].vector[log_ratio] < rows[0].vector[log_ratio]


def test_a_later_month_cannot_change_an_earlier_row():
    short = customer_features(months([10, 11, 12, 13, 14]), CONFIG)
    long = customer_features(months([10, 11, 12, 13, 14, 90, 90]), CONFIG)
    assert long[: len(short)] == short


def test_closed_months_are_skipped_and_do_not_distort_the_next_month():
    states = ["active", "active", "active", "active", "disconnected", "reconnection", "active"]
    gap = customer_features(months([10, 10, 10, 10, 0, 0, 10], states), CONFIG)
    assert [r.month for r in gap] == [4, 7]
    assert gap[1].vector == customer_features(months([10] * 5), CONFIG)[1].vector


def test_a_customer_with_no_month_after_the_baseline_has_no_rows():
    assert customer_features(months([10, 10, 10]), CONFIG) == []


def test_a_month_a_rule_catches_records_the_rule():
    rows = customer_features(months([10, 10, 10, 400]), CONFIG)
    assert rows[0].rule_type == "SPIKE"


def test_split_keeps_each_customer_on_one_side_and_keeps_the_mix(simulation):
    train, test = split_customers(simulation.customers, seed=42)
    assert not set(train) & set(test)
    assert len(train) + len(test) == 120 and len(test) == 36
    kinds = {c.customer_id: c.customer_type for c in simulation.customers}
    assert sum(kinds[c] == "commercial" for c in test) == pytest.approx(0.3 * 12, abs=1)


def test_only_test_customers_are_reported_and_training_used_no_rule_caught_month(simulation, result):
    assert {d.customer_id for d in result.detections} <= set(result.test_customers)
    observations = observations_from_ledger(simulation.ledger)
    rows = [r for c in result.train_customers for r in customer_features(observations[c], CONFIG)]
    assert result.model.n_samples == sum(r.rule_type is None for r in rows)


def test_every_active_fault_month_of_a_test_customer_is_scored(simulation, result):
    scored = {(d.customer_id, d.month) for d in result.detections}
    faults = [r for r in simulation.ledger if r.ground_truth_anomaly and r.customer_id in set(result.test_customers)]
    assert faults and all((r.customer_id, r.month) in scored for r in faults)


def test_closed_months_are_never_scored(simulation, result):
    closed = {(r.customer_id, r.month) for r in simulation.ledger if r.state != "active"}
    assert closed.isdisjoint((d.customer_id, d.month) for d in result.detections)


def test_a_bulk_score_equals_the_app_model_score(simulation):
    observations = observations_from_ledger(simulation.ledger)
    rows = [r for cid in list(observations)[:40] for r in customer_features(observations[cid], CONFIG)]
    model = train_forest(rows, CONFIG)
    for row, detection in list(zip(rows, score_months(model, rows)))[:5]:
        assert model.score(row.vector) == (detection.anomaly_score, detection.forest_flag)


def test_same_seed_gives_identical_detections(simulation, result):
    assert run_detection(simulation).detections == result.detections


def test_detection_does_not_save_a_model_for_the_app(simulation, tmp_path):
    path = tmp_path / "isolation_forest.joblib"
    run_detection(simulation, replace(CONFIG, model_path=path))
    assert not path.exists()


def test_csv_holds_the_agreed_columns_and_no_labels(result, tmp_path):
    path = write_detections(result.detections, tmp_path)
    with path.open(encoding="utf-8") as handle:
        header = next(csv.reader(handle))
    assert header == [f.name for f in fields(Detection)]
    assert "ground_truth_anomaly" not in header and "anomaly_type" not in header
