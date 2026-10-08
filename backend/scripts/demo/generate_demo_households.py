"""Generate DEMO households so the anomaly pipeline can be exercised before WASAC data arrives.

    python scripts/demo/generate_demo_households.py                # writes the demo CSV
    python scripts/demo/generate_demo_households.py --load-db      # also inserts DEMO- rows into the DB

Everything produced here is synthetic and prefixed "DEMO-". Do not report results computed on it.
"""
import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _data import DEMO_BANNER  # noqa: E402

from anomaly.demo_data import generate_demo_histories  # noqa: E402

DEFAULT_OUT = Path(__file__).resolve().parent / "output" / "DEMO_households.csv"


def write_csv(histories, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["household_id", "reading_date", "reading_m3", "is_demo"])
        for hid, points in histories.items():
            for p in points:
                w.writerow([hid, p.date.isoformat(), f"{p.reading_m3:.3f}", "true"])


def load_into_db(histories) -> int:
    from database import Base, Customer, Meter, Reading, SessionLocal, engine
    import anomaly.db_models  # noqa: F401  registers anomaly_flags

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    added = 0
    try:
        for hid, points in histories.items():
            if db.query(Meter).filter(Meter.meter_id == hid).first():
                continue
            customer_id = hid.replace("MTR", "CUST")
            # meters and customers reference each other, so link them after both rows exist.
            meter = Meter(meter_id=hid, last_reading=points[-1].reading_m3, last_reading_date=points[-1].date)
            db.add(meter)
            db.flush()
            db.add(Customer(customer_id=customer_id, name=f"DEMO Household {hid[-3:]}",
                            phone="+250700000000", meter_id=hid, sector="DEMO"))
            db.flush()
            meter.customer_id = customer_id
            prev = None
            for p in points:
                db.add(Reading(meter_id=hid, submitted_value=p.reading_m3,
                               implied_consumption=None if prev is None else round(p.reading_m3 - prev, 3),
                               submission_method="demo", validation_status="valid",
                               submission_time=p.date))
                prev = p.reading_m3
            added += 1
        db.commit()
    finally:
        db.close()
    return added


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--households", type=int, default=20)
    parser.add_argument("--readings", type=int, default=24)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--load-db", action="store_true", help="Also insert DEMO- meters/readings into DATABASE_URL")
    args = parser.parse_args()

    print(DEMO_BANNER)
    histories = generate_demo_histories(args.households, args.readings, args.seed)
    write_csv(histories, args.out)
    print(f"Wrote {len(histories)} DEMO households x {args.readings} readings to {args.out}")
    if args.load_db:
        print(f"Inserted {load_into_db(histories)} DEMO households into the database (existing ones skipped).")


if __name__ == "__main__":
    main()
