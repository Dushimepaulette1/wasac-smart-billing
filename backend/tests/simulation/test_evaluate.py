"""The simulation's evaluation: the metrics, customer-level intervals, and the saved results."""
import json

import numpy as np
import pytest

from simulation.config import SimulationConfig
from simulation.detect import run_detection
from simulation.evaluate import (
    COMBINED, FOREST, RULES, SETUPS, Confusion, ScoredMonth, blind_spots, bootstrap_draws, build_report, confusion,
    customer_counts, detection_delay, join_labels, metrics_from_totals, write_confusion_plot, write_metrics,
)
from simulation.ledger import run_simulation

SMALL = SimulationConfig(n_customers=120)


def month(customer="C1", number=4, fault="none", rule=False, forest=False, kind="domestic"):
    return ScoredMonth(customer, kind, number, fault, rule, forest)


@pytest.fixture(scope="module")
def run():
    simulation = run_simulation(SMALL)
    return simulation, run_detection(simulation)


@pytest.fixture(scope="module")
def report(run):
    return build_report(*run, n_bootstrap=200, n_seeds=2)


def test_metrics_from_a_known_confusion():
    found = Confusion(tp=8, fp=2, fn=8, tn=82)
    assert found.precision == 0.8
    assert found.recall == 0.5
    assert found.f1 == pytest.approx(2 * 0.8 * 0.5 / 1.3)
    assert found.false_alarm_rate == pytest.approx(2 / 84)


def test_metrics_with_nothing_to_divide_by_are_zero():
    empty = Confusion()
    assert (empty.precision, empty.recall, empty.f1, empty.false_alarm_rate) == (0.0, 0.0, 0.0, 0.0)


def test_many_rows_at_once_match_the_single_calculation():
    found = Confusion(tp=8, fp=2, fn=8, tn=82)
    bulk = metrics_from_totals(np.array([[8, 2, 8, 82], [0, 0, 0, 0]]))
    assert bulk["f1"][0] == pytest.approx(found.f1)
    assert bulk["precision"][1] == 0.0


def test_rules_plus_forest_flags_when_either_does():
    assert not month().flagged(COMBINED)
    assert month(rule=True).flagged(COMBINED)
    assert month(forest=True).flagged(COMBINED)
    assert month(rule=True).flagged(RULES) and not month(rule=True).flagged(FOREST)


def test_confusion_counts_each_outcome():
    months = [month(fault="leak", rule=True), month(fault="bypass"), month(rule=True), month()]
    assert confusion(months, RULES) == Confusion(tp=1, fp=1, fn=1, tn=1)


def test_customer_counts_add_up_to_the_confusion():
    months = [month("A", fault="leak", rule=True), month("A"), month("B", rule=True)]
    counts = customer_counts(months, ["A", "B", "C"], RULES)
    assert counts.tolist() == [[1, 0, 0, 1], [0, 1, 0, 0], [0, 0, 0, 0]]


def test_resamples_pick_whole_customers_and_repeat_with_the_seed():
    draws = bootstrap_draws(10, 50, seed=1)
    assert draws.shape == (50, 10) and draws.max() < 10
    assert np.array_equal(draws, bootstrap_draws(10, 50, seed=1))
    assert not np.array_equal(draws, bootstrap_draws(10, 50, seed=2))


def test_delay_counts_fault_months_before_the_first_flag():
    months = [month("A", 4, "leak"), month("A", 5, "leak"), month("A", 6, "leak", forest=True),
              month("B", 4, "bypass", forest=True), month("C", 4, "leak")]
    assert detection_delay(months, FOREST) == {
        "faults": 3, "faults_caught": 2, "mean_fault_months_before_first_flag": 1.0,
    }


def test_delay_when_nothing_is_caught():
    assert detection_delay([month(fault="leak")], RULES)["mean_fault_months_before_first_flag"] is None


def test_blind_spots_split_by_customer_type_and_fault():
    months = [month(fault="bypass"), month(fault="leak", rule=True), month(rule=True, kind="commercial"),
              month(kind="commercial")]
    found = blind_spots(months, RULES)
    assert found["missed_fault_months"]["domestic_bypass"] == 1
    assert found["missed_fault_months"]["domestic_leak"] == 0
    assert found["false_alarms"]["commercial"] == {"false_alarms": 1, "normal_months": 2, "rate": 0.5}


def test_labels_join_every_detection_to_the_ledger(run):
    simulation, result = run
    months = join_labels(simulation, result.detections)
    assert len(months) == len(result.detections)
    truth = {(r.customer_id, r.month): r.ground_truth_anomaly for r in simulation.ledger}
    assert all(truth[(m.customer_id, m.month)] == int(m.is_fault) for m in months)


def test_each_interval_holds_its_value(report):
    for setup in SETUPS:
        for metric in ("precision", "recall", "f1", "false_alarm_rate"):
            estimate = report["setups"][setup][metric]
            assert estimate["ci_low"] <= estimate["value"] <= estimate["ci_high"]


def test_combined_never_catches_less_than_either_setup(report):
    tp = {setup: report["setups"][setup]["confusion"]["tp"] for setup in SETUPS}
    assert tp[COMBINED] >= max(tp[RULES], tp[FOREST])


def test_every_setup_sees_the_same_months(report):
    for setup in SETUPS:
        assert sum(report["setups"][setup]["confusion"].values()) == report["test_months"]


def test_recall_by_fault_adds_up_to_all_faults(report):
    parts = report["setups"][FOREST]["recall_by_fault"]
    assert parts["leak"]["total"] + parts["bypass"]["total"] == report["fault_months"]


def test_difference_is_the_gap_between_the_two_setups(report):
    gap = report["setups"][FOREST]["f1"]["value"] - report["setups"][RULES]["f1"]["value"]
    assert report["differences"]["forest_minus_rules"]["f1"]["value"] == pytest.approx(gap, abs=0.0002)


def test_subtle_faults_are_harder_for_the_rules(report):
    assert report["subtle_faults"]["setups"][RULES]["recall"]["value"] < report["setups"][RULES]["recall"]["value"]


def test_seed_study_leaves_out_the_headline_seed(report):
    assert report["seed_study"]["seeds"] == [43, 44]
    f1 = report["seed_study"]["setups"][FOREST]["f1"]
    assert f1["min"] <= f1["mean"] <= f1["max"]


def test_metrics_file_is_valid_json_and_says_the_data_is_synthetic(report, tmp_path):
    saved = json.loads(write_metrics(report, tmp_path).read_text(encoding="utf-8"))
    assert saved["notice"].startswith("Synthetic data")
    assert saved["assumptions"]["seed"] == 42
    assert saved["bootstrap"]["unit"] == "customer"


def test_confusion_plot_is_saved(report, tmp_path):
    pytest.importorskip("matplotlib")
    path = write_confusion_plot(report, tmp_path)
    assert path.name == "confusion_matrices.png"
    assert path.read_bytes().startswith(b"\x89PNG")
