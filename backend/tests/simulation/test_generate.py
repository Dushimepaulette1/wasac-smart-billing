"""The simulation's data generator: distributions, reproducibility and fault placement."""
import math
from dataclasses import replace
from statistics import median

import numpy as np
import pytest

from simulation.config import (
    BYPASS, COMMERCIAL, COMMERCIAL_PROFILE, DOMESTIC, DOMESTIC_PROFILE, LEAK, ConsumptionProfile, SimulationConfig,
)
from simulation.generate import RandomStreams, _eligible_start_months, generate_customers, schedule_faults
from simulation.ledger import run_simulation


def test_log_normal_parameters_match_the_stated_ranges():
    assert DOMESTIC_PROFILE.mu == pytest.approx(2.414, abs=0.001)
    assert DOMESTIC_PROFILE.sigma == pytest.approx(0.489, abs=0.001)
    assert COMMERCIAL_PROFILE.mu == pytest.approx(4.605, abs=0.001)
    assert COMMERCIAL_PROFILE.sigma == pytest.approx(0.421, abs=0.001)


def test_a_profile_with_a_backwards_range_is_refused():
    with pytest.raises(ValueError):
        ConsumptionProfile(DOMESTIC, share=1.0, low_m3=25.0, high_m3=5.0, noise_sigma=0.1, pay_probability=0.9)


def test_profile_shares_must_add_up_to_one():
    with pytest.raises(ValueError):
        SimulationConfig(profiles=(DOMESTIC_PROFILE,  replace(COMMERCIAL_PROFILE, share=0.5)))


def test_customers_follow_the_configured_mix_and_ranges():
    config = SimulationConfig(n_customers=20_000)
    customers = generate_customers(config, np.random.default_rng(1))
    domestic = [c.baseline_mean_m3 for c in customers if c.customer_type == DOMESTIC]
    commercial = [c.baseline_mean_m3 for c in customers if c.customer_type == COMMERCIAL]
    assert len(commercial) == 2_000
    assert median(domestic) == pytest.approx(math.sqrt(5 * 25), rel=0.03)
    assert median(commercial) == pytest.approx(100, rel=0.03)
    assert sum(5 <= v <= 25 for v in domestic) / len(domestic) == pytest.approx(0.90, abs=0.015)
    assert sum(50 <= v <= 200 for v in commercial) / len(commercial) == pytest.approx(0.90, abs=0.02)


def test_every_customer_id_is_marked_as_demo_data():
    assert all(c.customer_id.startswith("DEMO-") for c in run_simulation().customers)


def test_the_same_seed_gives_identical_data_and_another_seed_does_not():
    first = run_simulation(SimulationConfig(n_customers=100))
    assert first.ledger == run_simulation(SimulationConfig(n_customers=100)).ledger
    assert first.events == run_simulation(SimulationConfig(n_customers=100)).events
    assert first.ledger != run_simulation(SimulationConfig(n_customers=100, seed=43)).ledger


def test_changing_the_fault_rate_does_not_change_customers():
    config = SimulationConfig(n_customers=100)
    other = replace(config, faults=replace(config.faults, share_of_active_months=0.10))
    assert run_simulation(config).customers == run_simulation(other).customers


def test_a_fault_may_only_start_after_clean_active_months():
    active = [True, False, True, True, True, False, True]
    assert _eligible_start_months(active, 3) == [5, 7]


@pytest.mark.parametrize("seed", [1, 2, 3, 42])
def test_fault_months_are_five_percent_of_active_months_and_never_more(seed):
    simulation = run_simulation(SimulationConfig(seed=seed))
    active = sum(r.state == "active" for r in simulation.ledger)
    labelled = sum(r.ground_truth_anomaly for r in simulation.ledger)
    assert labelled <= round(active * 0.05)
    assert labelled / active == pytest.approx(0.05, abs=0.001)


def test_both_kinds_of_fault_are_injected_within_their_ranges():
    events = run_simulation().events
    leaks = [e for e in events if e.anomaly_type == LEAK]
    bypasses = [e for e in events if e.anomaly_type == BYPASS]
    assert leaks and bypasses
    assert all(3.0 <= e.multiplier <= 5.0 for e in leaks)
    assert all(0.0 <= e.multiplier <= 0.05 for e in bypasses)


def test_a_customer_has_at_most_one_fault():
    events = run_simulation().events
    assert len({e.customer_id for e in events}) == len(events)


def test_when_no_customer_is_eligible_no_fault_is_placed():
    config = SimulationConfig(n_customers=2, n_months=3)
    flags = {"A": [True, True, True], "B": [True, False, True]}
    assert schedule_faults(flags, config, RandomStreams.from_seed(1).faults) == []
