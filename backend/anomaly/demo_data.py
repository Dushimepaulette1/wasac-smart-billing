"""DEMO-ONLY synthetic household histories for exercising the pipeline before WASAC data arrives.

Every household id starts with "DEMO-". Never use these numbers as evidence of real performance.
"""
import random
from datetime import datetime, timedelta
from typing import Dict, List

from anomaly.features import ReadingPoint

DEMO_PREFIX = "DEMO-"


def generate_demo_histories(
    n_households: int = 20,
    n_readings: int = 24,
    seed: int = 7,
    start: datetime = datetime(2024, 1, 5, 9, 0),
) -> Dict[str, List[ReadingPoint]]:
    """Plausible Kigali residential histories: ~0.3-1.2 m3/day, irregular 24-38 day gaps,
    mild dry-season uplift (Jun-Aug) and ~12% period-to-period noise. No injected anomalies."""
    rng = random.Random(seed)
    histories = {}
    for i in range(1, n_households + 1):
        base_daily = rng.lognormvariate(-0.55, 0.35)
        reading = round(rng.uniform(100, 900), 3)
        when = start + timedelta(days=rng.randint(0, 20), hours=rng.randint(0, 9))
        points = [ReadingPoint(date=when, reading_m3=reading)]
        for _ in range(n_readings - 1):
            days = rng.randint(24, 38)
            when = when + timedelta(days=days, hours=rng.randint(-3, 3))
            season = 1.15 if when.month in (6, 7, 8) else 1.0
            daily = base_daily * season * rng.lognormvariate(0, 0.12)
            reading = round(reading + daily * days, 3)
            points.append(ReadingPoint(date=when, reading_m3=reading))
        histories[f"{DEMO_PREFIX}MTR-{i:03d}"] = points
    return histories
