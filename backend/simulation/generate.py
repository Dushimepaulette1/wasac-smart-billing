"""Phase 1: synthetic customers, their monthly use, payment behaviour and injected faults.

Each kind of random draw has its own stream, so changing one assumption (the fault rate, say) does
not reshuffle customers or payments. Payment behaviour is drawn without looking at bill amounts,
which lets the ledger's states be known before faults are placed on Active months.
"""
from dataclasses import dataclass
from typing import Dict, List, Mapping, Sequence

import numpy as np

from simulation.config import BYPASS, LEAK, ConsumptionProfile, SimulationConfig

ID_PREFIX = "DEMO-SIM-"  # DEMO-: excluded from model training on app data


@dataclass(frozen=True)
class Customer:
    customer_id: str
    customer_type: str
    baseline_mean_m3: float
    noise_sigma: float
    opening_reading_m3: float
    pay_probability: float
    seed: int


@dataclass(frozen=True)
class PaymentBehaviour:
    """Index 0 is month 1. A draw is used only if the customer reaches the matching state."""

    pays_bill: Sequence[bool]
    pays_arrears: Sequence[bool]


@dataclass(frozen=True)
class AnomalyEvent:
    event_id: int
    customer_id: str
    anomaly_type: str
    start_month: int
    end_month: int  # inclusive
    multiplier: float

    def covers(self, month: int) -> bool:
        return self.start_month <= month <= self.end_month


@dataclass(frozen=True)
class RandomStreams:
    customers: np.random.Generator
    volumes: np.random.Generator
    payments: np.random.Generator
    faults: np.random.Generator

    @classmethod
    def from_seed(cls, seed: int) -> "RandomStreams":
        children = np.random.SeedSequence(seed).spawn(4)
        return cls(*(np.random.default_rng(child) for child in children))


def _draw_profiles(config: SimulationConfig, rng: np.random.Generator) -> List[ConsumptionProfile]:
    """Exactly the configured mix (rounded), in random order: not left to chance on a small sample."""
    profiles: List[ConsumptionProfile] = []
    for profile in config.profiles[1:]:
        profiles += [profile] * round(config.n_customers * profile.share)
    profiles += [config.profiles[0]] * (config.n_customers - len(profiles))
    rng.shuffle(profiles)
    return profiles


def generate_customers(config: SimulationConfig, rng: np.random.Generator) -> List[Customer]:
    low, high = config.opening_reading_m3
    customers = []
    for number, profile in enumerate(_draw_profiles(config, rng), start=1):
        customers.append(Customer(
            customer_id=f"{ID_PREFIX}{number:04d}",
            customer_type=profile.customer_type,
            baseline_mean_m3=round(float(rng.lognormal(profile.mu, profile.sigma)), 3),
            noise_sigma=profile.noise_sigma,
            opening_reading_m3=round(float(rng.uniform(low, high)), 3),
            pay_probability=profile.pay_probability,
            seed=config.seed,
        ))
    return customers


def generate_normal_volumes(
    customers: Sequence[Customer], config: SimulationConfig, rng: np.random.Generator
) -> Dict[str, List[float]]:
    """Every month's use with no fault and water on. The -sigma^2/2 keeps each customer's long-run
    mean at their baseline. Drawn for all months, so a disconnection cannot shift the later draws."""
    volumes = {}
    for customer in customers:
        sigma = customer.noise_sigma
        noise = rng.lognormal(-(sigma ** 2) / 2, sigma, config.n_months)
        volumes[customer.customer_id] = [float(customer.baseline_mean_m3 * n) for n in noise]
    return volumes


def generate_payment_behaviour(
    customers: Sequence[Customer], config: SimulationConfig, rng: np.random.Generator
) -> Dict[str, PaymentBehaviour]:
    behaviour = {}
    for customer in customers:
        pays_bill = rng.random(config.n_months) < customer.pay_probability
        pays_arrears = rng.random(config.n_months) < config.pay_arrears_probability
        behaviour[customer.customer_id] = PaymentBehaviour(
            pays_bill=[bool(v) for v in pays_bill], pays_arrears=[bool(v) for v in pays_arrears],
        )
    return behaviour


def _eligible_start_months(active: Sequence[bool], clean_months: int) -> List[int]:
    """Active months (1-based) that follow at least clean_months earlier Active months."""
    months = []
    seen = 0
    for month, is_active in enumerate(active, start=1):
        if is_active:
            if seen >= clean_months:
                months.append(month)
            seen += 1
    return months


def schedule_faults(
    active_months: Mapping[str, Sequence[bool]], config: SimulationConfig, rng: np.random.Generator
) -> List[AnomalyEvent]:
    """Place one fault at most per customer until the target share of Active months is reached.

    The target counts labelled months only: a month inside an event but not Active is not a fault
    month. A fault too long for what remains is shortened, or skipped if that would make it shorter
    than its minimum, so the share lands just under the target and never over it.
    """
    settings = config.faults
    total_active = sum(sum(flags) for flags in active_months.values())
    target = round(total_active * settings.share_of_active_months)
    customer_ids = list(active_months)
    rng.shuffle(customer_ids)

    events: List[AnomalyEvent] = []
    labelled = 0
    for customer_id in customer_ids:
        remaining = target - labelled
        if remaining <= 0:
            break
        active = active_months[customer_id]
        starts = _eligible_start_months(active, settings.clean_months)
        if not starts:
            continue
        leak = bool(rng.random() < settings.leak_share)
        low_months, high_months = settings.leak_months if leak else settings.bypass_months
        low_scale, high_scale = settings.leak_multiplier if leak else settings.bypass_multiplier
        start = int(rng.choice(starts))
        wanted = int(rng.integers(low_months, high_months + 1))
        scale = float(rng.uniform(low_scale, high_scale))

        end = min(start + wanted - 1, config.n_months)
        covered = [m for m in range(start, end + 1) if active[m - 1]]
        covered = covered[:remaining]
        if len(covered) < low_months:
            continue  # too short to be a fault of this kind: the year or the target ran out
        if covered[-1] < end:
            end = covered[-1]
        events.append(AnomalyEvent(
            event_id=len(events) + 1, customer_id=customer_id, anomaly_type=LEAK if leak else BYPASS,
            start_month=start, end_month=end, multiplier=round(scale, 4),
        ))
        labelled += len(covered)
    return events
