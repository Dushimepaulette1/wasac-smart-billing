"""Phase 2: the month-by-month billing state machine, and the simulation's CSV files.

Month N depends only on month N-1 (transition):

    ACTIVE        bill paid                     -> ACTIVE
    ACTIVE        bill unpaid                   -> DISCONNECTED
    DISCONNECTED  no "pay arrears" event        -> DISCONNECTED
    DISCONNECTED  "pay arrears" event           -> RECONNECTION
    RECONNECTION                                -> ACTIVE

Only an ACTIVE month has water use and a bill. A RECONNECTION month records the arrears and the
penalty being paid; supply returns the following month. Faults are not labelled outside ACTIVE
months, so closed water is never counted as fraud.
"""
import csv
from dataclasses import asdict, dataclass, fields
from enum import Enum
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence

from app.services.billing import calculate_bill
from simulation.config import SimulationConfig
from simulation.generate import (
    AnomalyEvent, Customer, PaymentBehaviour, RandomStreams, generate_customers, generate_normal_volumes,
    generate_payment_behaviour, schedule_faults,
)

PAID = "paid"
UNPAID = "unpaid"
NO_BILL = "none"
NO_ANOMALY = "none"


class State(str, Enum):
    ACTIVE = "active"
    DISCONNECTED = "disconnected"
    RECONNECTION = "reconnection"


def transition(previous: State, bill_paid: bool, arrears_event: bool) -> State:
    """The state of month N from month N-1 (see the module docstring)."""
    if previous is State.ACTIVE:
        return State.ACTIVE if bill_paid else State.DISCONNECTED
    if previous is State.DISCONNECTED:
        return State.RECONNECTION if arrears_event else State.DISCONNECTED
    return State.ACTIVE


def state_timeline(behaviour: PaymentBehaviour, n_months: int) -> List[State]:
    """Every month's state. Month 1 has no earlier bill, so it starts ACTIVE."""
    states = [State.ACTIVE]
    for month in range(1, n_months):
        states.append(transition(states[-1], behaviour.pays_bill[month - 1], behaviour.pays_arrears[month - 1]))
    return states


@dataclass(frozen=True)
class LedgerRow:
    customer_id: str
    month: int
    state: str
    opening_reading_m3: float
    closing_reading_m3: float
    volume_m3: float
    bill_amount_rwf: Optional[float]
    tariff_version: Optional[str]
    bill_status: str
    arrears_rwf: float  # still owed at the end of this month
    penalty_rwf: float
    payment_rwf: float
    water_closed_flag: bool
    consecutive_unpaid_months: int  # counted before this month
    ground_truth_anomaly: int
    anomaly_type: str


def faulty_volume(normal_m3: float, event: AnomalyEvent) -> float:
    return normal_m3 * event.multiplier


def build_customer_ledger(
    customer: Customer,
    normal_volumes: Sequence[float],
    behaviour: PaymentBehaviour,
    event: Optional[AnomalyEvent],
    config: SimulationConfig,
) -> List[LedgerRow]:
    rows: List[LedgerRow] = []
    reading = customer.opening_reading_m3
    arrears = 0.0
    unpaid_months = 0
    states = state_timeline(behaviour, config.n_months)

    for index, state in enumerate(states):
        month = index + 1
        unpaid_before = unpaid_months
        volume = 0.0
        bill: Optional[float] = None
        tariff_version: Optional[str] = None
        bill_status = NO_BILL
        penalty = 0.0
        payment = 0.0
        faulty = False

        if state is State.ACTIVE:
            faulty = event is not None and event.covers(month)
            volume = faulty_volume(normal_volumes[index], event) if faulty else normal_volumes[index]
            volume = round(volume, 3)
            bill = calculate_bill(volume, config.tariff_version)["total"]
            tariff_version = config.tariff_version
            if behaviour.pays_bill[index]:
                bill_status = PAID
                payment = bill
                unpaid_months = 0
            else:
                bill_status = UNPAID
                arrears = round(arrears + bill, 2)
                unpaid_months += 1
        elif state is State.RECONNECTION:
            penalty = config.penalty_rwf
            payment = round(arrears + penalty, 2)
            arrears = 0.0
            unpaid_months = 0

        closing = round(reading + volume, 3)
        rows.append(LedgerRow(
            customer_id=customer.customer_id,
            month=month,
            state=state.value,
            opening_reading_m3=reading,
            closing_reading_m3=closing,
            volume_m3=volume,
            bill_amount_rwf=bill,
            tariff_version=tariff_version,
            bill_status=bill_status,
            arrears_rwf=arrears,
            penalty_rwf=penalty,
            payment_rwf=payment,
            water_closed_flag=state is State.DISCONNECTED,
            consecutive_unpaid_months=unpaid_before,
            ground_truth_anomaly=int(faulty),
            anomaly_type=event.anomaly_type if faulty else NO_ANOMALY,
        ))
        reading = closing
    return rows


@dataclass(frozen=True)
class Simulation:
    config: SimulationConfig
    customers: List[Customer]
    events: List[AnomalyEvent]
    ledger: List[LedgerRow]


def active_flags(behaviour: Mapping[str, PaymentBehaviour], n_months: int) -> Dict[str, List[bool]]:
    return {
        customer_id: [state is State.ACTIVE for state in state_timeline(payments, n_months)]
        for customer_id, payments in behaviour.items()
    }


def run_simulation(config: Optional[SimulationConfig] = None) -> Simulation:
    config = config or SimulationConfig()
    streams = RandomStreams.from_seed(config.seed)
    customers = generate_customers(config, streams.customers)
    volumes = generate_normal_volumes(customers, config, streams.volumes)
    behaviour = generate_payment_behaviour(customers, config, streams.payments)
    events = schedule_faults(active_flags(behaviour, config.n_months), config, streams.faults)

    by_customer = {event.customer_id: event for event in events}
    ledger: List[LedgerRow] = []
    for customer in customers:
        ledger += build_customer_ledger(
            customer, volumes[customer.customer_id], behaviour[customer.customer_id],
            by_customer.get(customer.customer_id), config,
        )
    return Simulation(config=config, customers=customers, events=events, ledger=ledger)


CUSTOMER_COLUMNS = ("customer_id", "customer_type", "baseline_mean_m3", "noise_sigma", "seed")


def _write_csv(path: Path, columns: Sequence[str], rows: Iterable[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_outputs(simulation: Simulation, output_dir: Path) -> List[Path]:
    """customers.csv, ledger.csv and anomaly_events.csv. The default folder is gitignored."""
    output_dir.mkdir(parents=True, exist_ok=True)
    customers = output_dir / "customers.csv"
    ledger = output_dir / "ledger.csv"
    events = output_dir / "anomaly_events.csv"
    _write_csv(customers, CUSTOMER_COLUMNS, (asdict(c) for c in simulation.customers))
    _write_csv(ledger, [f.name for f in fields(LedgerRow)], (asdict(r) for r in simulation.ledger))
    _write_csv(events, [f.name for f in fields(AnomalyEvent)], (asdict(e) for e in simulation.events))
    return [customers, ledger, events]
