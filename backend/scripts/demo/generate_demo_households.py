"""Generate DEMO households so the anomaly pipeline can be exercised before WASAC data arrives.

    python scripts/demo/generate_demo_households.py                # writes the demo CSV
    python scripts/demo/generate_demo_households.py --load-db      # also inserts DEMO- rows into the DB
    python scripts/demo/generate_demo_households.py --update-contacts   # phones/locations of existing DEMO- rows

Sign-in: DEMO-MTR-001 uses phone 0700 000 001, DEMO-MTR-002 uses 0700 000 002, and so on;
the last two meters share one number, to show choosing between meters. The 07000000xx numbers
are not real Rwandan mobiles, and demo sign-in codes are shown on screen instead of sent.
DEMO-MTR-002 has a location on file (Kacyiru, Kigali), so its readings show the location check.

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
DEMO_GPS = {"DEMO-MTR-002": (-1.9441, 30.0619)}


def demo_phone(hid: str, households: int) -> str:
    n = int(hid[-3:])
    if households >= 2 and n == households:
        n -= 1  # the last two meters share a number
    return f"+250700000{n:03d}"


def update_contacts(histories) -> int:
    """Set the sign-in phone and location of DEMO- rows already in the database. Touches nothing else."""
    from database import Customer, Meter, SessionLocal

    db = SessionLocal()
    updated = 0
    try:
        for hid in histories:
            if not hid.startswith("DEMO-"):
                continue
            customer = db.query(Customer).filter(Customer.meter_id == hid).first()
            meter = db.query(Meter).filter(Meter.meter_id == hid).first()
            if not customer or not meter or not customer.customer_id.startswith("DEMO-"):
                continue
            customer.phone = demo_phone(hid, len(histories))
            meter.gps_lat, meter.gps_lng = DEMO_GPS.get(hid, (None, None))
            updated += 1
        db.commit()
    finally:
        db.close()
    return updated


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
            lat, lng = DEMO_GPS.get(hid, (None, None))
            meter = Meter(meter_id=hid, last_reading=points[-1].reading_m3, last_reading_date=points[-1].date,
                          gps_lat=lat, gps_lng=lng)
            db.add(meter)
            db.flush()
            db.add(Customer(customer_id=customer_id, name=f"DEMO Household {hid[-3:]}",
                            phone=demo_phone(hid, len(histories)), meter_id=hid, sector="DEMO"))
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
    parser.add_argument("--update-contacts", action="store_true",
                        help="Set sign-in phones and locations on DEMO- rows already in DATABASE_URL")
    args = parser.parse_args()

    print(DEMO_BANNER)
    histories = generate_demo_histories(args.households, args.readings, args.seed)
    write_csv(histories, args.out)
    print(f"Wrote {len(histories)} DEMO households x {args.readings} readings to {args.out}")
    if args.load_db:
        print(f"Inserted {load_into_db(histories)} DEMO households into the database (existing ones skipped).")
    if args.update_contacts:
        print(f"Updated the phone and location of {update_contacts(histories)} DEMO households.")


if __name__ == "__main__":
    main()
