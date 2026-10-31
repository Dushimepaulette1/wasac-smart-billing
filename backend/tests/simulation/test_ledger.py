"""The simulation's billing state machine and its CSV output."""
import csv
from collections import defaultdict

import pytest

from app.services.billing import calculate_bill
from simulation.config import SimulationConfig
from simulation.generate import AnomalyEvent, Customer, PaymentBehaviour
from simulation.ledger import (
    NO_BILL, PAID, UNPAID, State, build_customer_ledger, run_simulation, state_timeline, transition, write_outputs,
)

CONFIG = SimulationConfig(n_customers=1, n_months=6)
CUSTOMER = Customer("DEMO-SIM-0001", "domestic", 10.0, 0.15, 500.0, 0.95, 42)
USE = [10.0] * 6


def ledger(pays_bill, pays_arrears=(False,) * 6, event=None, config=CONFIG):
    return build_customer_ledger(CUSTOMER, USE, PaymentBehaviour(pays_bill, pays_arrears), event, config)


@pytest.mark.parametrize("previous, paid, event, expected", [
    (State.ACTIVE, True, False, State.ACTIVE),
    (State.ACTIVE, True, True, State.ACTIVE),
    (State.ACTIVE, False, False, State.DISCONNECTED),
    (State.ACTIVE, False, True, State.DISCONNECTED),
    (State.DISCONNECTED, False, False, State.DISCONNECTED),
    (State.DISCONNECTED, False, True, State.RECONNECTION),
    (State.RECONNECTION, False, False, State.ACTIVE),
    (State.RECONNECTION, True, True, State.ACTIVE),
])
def test_transitions(previous, paid, event, expected):
    assert transition(previous, paid, event) is expected


def test_month_one_starts_active_even_with_a_bad_payer():
    behaviour = PaymentBehaviour([False] * 3, [False] * 3)
    assert state_timeline(behaviour, 3) == [State.ACTIVE, State.DISCONNECTED, State.DISCONNECTED]


def test_a_paying_customer_stays_active_and_is_billed_every_month():
    rows = ledger([True] * 6)
    assert {r.state for r in rows} == {"active"}
    assert all(r.bill_status == PAID and r.payment_rwf == r.bill_amount_rwf for r in rows)
    assert rows[0].bill_amount_rwf == calculate_bill(10.0, CONFIG.tariff_version)["total"]


def test_after_an_unpaid_bill_water_closes_and_no_bill_is_made():
    rows = ledger([False, True, True, True, True, True])
    assert rows[0].bill_status == UNPAID
    assert rows[0].arrears_rwf == rows[0].bill_amount_rwf
    closed = rows[1]
    assert closed.state == "disconnected"
    assert closed.volume_m3 == 0
    assert closed.bill_amount_rwf is None and closed.tariff_version is None and closed.bill_status == NO_BILL
    assert closed.water_closed_flag is True
    assert closed.consecutive_unpaid_months == 1


def test_reconnection_pays_arrears_and_penalty_once_then_supply_returns():
    rows = ledger([False, True, True, True, True, True], [False, True, False, False, False, False])
    owed = rows[0].bill_amount_rwf
    assert [r.state for r in rows] == ["active", "disconnected", "reconnection", "active", "active", "active"]
    back = rows[2]
    assert back.payment_rwf == owed + 20_000
    assert back.penalty_rwf == 20_000 and back.arrears_rwf == 0
    assert back.volume_m3 == 0 and back.bill_amount_rwf is None and back.water_closed_flag is False
    assert rows[3].volume_m3 == 10.0 and rows[3].bill_status == PAID
    assert rows[3].consecutive_unpaid_months == 0
    assert sum(r.penalty_rwf for r in rows) == 20_000


def test_a_customer_who_never_pays_keeps_the_debt_with_no_penalty():
    rows = ledger([False] * 6)
    assert rows[-1].arrears_rwf == rows[0].bill_amount_rwf
    assert sum(r.penalty_rwf for r in rows) == 0
    assert sum(r.bill_status != NO_BILL for r in rows) == 1


def test_a_fault_changes_use_and_is_labelled_only_in_active_months():
    event = AnomalyEvent(1, CUSTOMER.customer_id, "leak", 2, 4, 4.0)
    rows = ledger([True, False, True, True, True, True], [False, False, True, False, False, False], event)
    assert [r.state for r in rows] == ["active", "active", "disconnected", "reconnection", "active", "active"]
    assert [r.ground_truth_anomaly for r in rows] == [0, 1, 0, 0, 0, 0]
    assert rows[1].volume_m3 == 40.0 and rows[1].anomaly_type == "leak"
    assert rows[2].volume_m3 == 0 and rows[2].anomaly_type == "none"


def test_a_bypass_drops_use_near_zero_while_the_account_stays_active():
    event = AnomalyEvent(1, CUSTOMER.customer_id, "bypass", 2, 3, 0.02)
    rows = ledger([True] * 6, event=event)
    assert rows[1].state == "active" and rows[1].volume_m3 == pytest.approx(0.2)
    assert rows[1].ground_truth_anomaly == 1 and rows[1].bill_amount_rwf is not None


def test_whole_run_keeps_the_ledger_rules():
    simulation = run_simulation()
    assert len(simulation.ledger) == 500 * 12
    by_customer = defaultdict(list)
    for row in simulation.ledger:
        by_customer[row.customer_id].append(row)
        assert row.closing_reading_m3 == pytest.approx(row.opening_reading_m3 + row.volume_m3, abs=0.0011)
        assert row.closing_reading_m3 >= row.opening_reading_m3
        if row.state != "active":
            assert row.volume_m3 == 0 and row.bill_amount_rwf is None and row.ground_truth_anomaly == 0
        if row.state == "disconnected":
            assert row.water_closed_flag
    for rows in by_customer.values():
        assert [r.month for r in rows] == list(range(1, 13))
        for before, after in zip(rows, rows[1:]):
            assert after.opening_reading_m3 == before.closing_reading_m3
            if before.bill_status == UNPAID:
                assert after.state == "disconnected"


def test_outputs_match_the_agreed_columns(tmp_path):
    customers, rows, events = write_outputs(run_simulation(SimulationConfig(n_customers=50)), tmp_path)
    with customers.open(encoding="utf-8") as handle:
        assert next(csv.reader(handle)) == ["customer_id", "customer_type", "baseline_mean_m3", "noise_sigma", "seed"]
    with rows.open(encoding="utf-8") as handle:
        header = next(csv.reader(handle))
    assert header[:2] == ["customer_id", "month"]
    assert header[-2:] == ["ground_truth_anomaly", "anomaly_type"]
    with events.open(encoding="utf-8") as handle:
        assert next(csv.reader(handle)) == [
            "event_id", "customer_id", "anomaly_type", "start_month", "end_month", "multiplier",
        ]
