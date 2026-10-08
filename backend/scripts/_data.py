"""Shared loaders for the anomaly training and evaluation scripts."""
import csv
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from anomaly.demo_data import DEMO_PREFIX  # noqa: E402
from anomaly.features import ReadingPoint  # noqa: E402
# seed_data() in database.py creates these three synthetic app-demo meters; they are not WASAC data.
SEED_METER_IDS = {"MTR001", "MTR002", "MTR003"}

Histories = Dict[str, List[ReadingPoint]]


def is_demo_id(household_id: str) -> bool:
    return household_id.startswith(DEMO_PREFIX)


def load_histories_csv(path: Path) -> Histories:
    """CSV columns: household_id, reading_date (ISO), reading_m3."""
    histories: Histories = defaultdict(list)
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            histories[row["household_id"]].append(
                ReadingPoint(
                    date=datetime.fromisoformat(row["reading_date"]),
                    reading_m3=float(row["reading_m3"]),
                )
            )
    return {k: sorted(v, key=lambda p: p.date) for k, v in histories.items()}


def load_histories_db(include_demo: bool = False, include_seed: bool = False) -> Histories:
    from database import Reading, SessionLocal

    db = SessionLocal()
    try:
        rows = (
            db.query(Reading.meter_id, Reading.submission_time, Reading.submitted_value)
            .order_by(Reading.meter_id, Reading.submission_time)
            .all()
        )
    finally:
        db.close()

    histories: Histories = defaultdict(list)
    for meter_id, when, value in rows:
        if is_demo_id(meter_id) and not include_demo:
            continue
        if meter_id in SEED_METER_IDS and not include_seed:
            continue
        histories[meter_id].append(ReadingPoint(date=when, reading_m3=value))
    return dict(histories)


def contains_demo(histories: Histories) -> bool:
    return any(is_demo_id(h) for h in histories)


DEMO_BANNER = (
    "\n" + "!" * 72 + "\n"
    "  DEMO DATA: synthetic households for pipeline testing only.\n"
    "  Results below are NOT a measurement of real WASAC performance.\n"
    "  Retrain and re-evaluate on real WASAC reading histories before reporting.\n"
    + "!" * 72 + "\n"
)
