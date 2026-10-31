"""Every assumption the simulation makes, in one place.

None of these values come from WASAC data. They are stated in the report as assumptions, including
the 20,000 RWF penalty and disconnection after one unpaid bill.
"""
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Tuple

DOMESTIC = "domestic"
COMMERCIAL = "commercial"
LEAK = "leak"
BYPASS = "bypass"

# Share of a standard normal distribution below this value is 95%: a stated range is treated as the
# 5th to 95th percentile of the customers' baselines.
Z_95 = 1.6448536269514722
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "output"


@dataclass(frozen=True)
class ConsumptionProfile:
    """How one type of customer uses water, in m3 per month."""

    customer_type: str
    share: float  # share of all customers
    low_m3: float  # 5th percentile of baselines
    high_m3: float  # 95th percentile of baselines
    noise_sigma: float  # log-normal month-to-month variation around a customer's baseline
    pay_probability: float  # chance that a given bill is paid in its month

    def __post_init__(self) -> None:
        if not 0 < self.low_m3 < self.high_m3:
            raise ValueError("A profile needs 0 < low_m3 < high_m3.")

    @property
    def mu(self) -> float:
        """Log-normal location: the log of the geometric middle of the range."""
        return (math.log(self.low_m3) + math.log(self.high_m3)) / 2

    @property
    def sigma(self) -> float:
        """Log-normal spread that puts low_m3 and high_m3 at the 5th and 95th percentiles."""
        return (math.log(self.high_m3) - math.log(self.low_m3)) / (2 * Z_95)


DOMESTIC_PROFILE = ConsumptionProfile(DOMESTIC, share=0.90, low_m3=5.0, high_m3=25.0, noise_sigma=0.15, pay_probability=0.95)
COMMERCIAL_PROFILE = ConsumptionProfile(COMMERCIAL, share=0.10, low_m3=50.0, high_m3=200.0, noise_sigma=0.35, pay_probability=0.97)


@dataclass(frozen=True)
class FaultConfig:
    """Injected faults. multiplier scales the customer's use while the fault lasts."""

    share_of_active_months: float = 0.05
    leak_share: float = 0.5  # the rest are bypasses
    leak_multiplier: Tuple[float, float] = (3.0, 5.0)
    leak_months: Tuple[int, int] = (3, 6)
    bypass_multiplier: Tuple[float, float] = (0.0, 0.05)
    bypass_months: Tuple[int, int] = (2, 6)
    # Active months a customer needs before a fault may start, so detection has a clean baseline.
    clean_months: int = 3


@dataclass(frozen=True)
class SimulationConfig:
    seed: int = 42
    n_customers: int = 500
    n_months: int = 12
    profiles: Tuple[ConsumptionProfile, ...] = (DOMESTIC_PROFILE, COMMERCIAL_PROFILE)
    faults: FaultConfig = field(default_factory=FaultConfig)
    opening_reading_m3: Tuple[float, float] = (100.0, 900.0)
    pay_arrears_probability: float = 0.5  # chance per disconnected month of a "pay arrears" event
    penalty_rwf: float = 20_000.0
    tariff_version: str = "v1-provisional"  # every customer type: the app has one tariff

    def __post_init__(self) -> None:
        if self.n_customers < 1 or self.n_months < 1:
            raise ValueError("The simulation needs at least one customer and one month.")
        if not math.isclose(sum(p.share for p in self.profiles), 1.0):
            raise ValueError("Profile shares must add up to 1.")
