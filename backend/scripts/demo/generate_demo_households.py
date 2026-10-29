"""Generate DEMO households so the anomaly pipeline can be exercised before WASAC data arrives.

    python scripts/demo/generate_demo_households.py                # writes the demo CSV
    python scripts/demo/generate_demo_households.py --load-db      # also inserts DEMO- rows into the DB
    python scripts/demo/generate_demo_households.py --update-contacts   # phones/locations of existing DEMO- rows
    python scripts/demo/generate_demo_households.py --set-phone KGL-20001 0788123456
                                                    # sign in to that DEMO household with your own phone
    python scripts/demo/generate_demo_households.py --rename-meters   # DEMO-MTR-001 -> KGL-20001 in the DB

Household 001 has meter KGL-20001 and signs in with 0700 000 001, household 002 has KGL-20002 and
0700 000 002, and so on; the last two meters share one number, to show choosing between meters.
The 07000000xx numbers are not real Rwandan mobiles, and demo sign-in codes are shown on screen
instead of sent. Household 002 has a location on file (Kacyiru, Kigali), so its readings show the
location check.

Everything produced here is synthetic. Each household's customer number starts with "DEMO-" (the
marker the app and the training scripts use); its meter has an ordinary-looking number so the app
reads naturally in a demo. Do not report results computed on it.
"""
import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _data import DEMO_BANNER  # noqa: E402

from app.anomaly.demo_data import generate_demo_histories  # noqa: E402

DEFAULT_OUT = Path(__file__).resolve().parent / "output" / "DEMO_households.csv"
DEMO_GPS = {"DEMO-MTR-002": (-1.9441, 30.0619)}
SECTORS = ("Kacyiru", "Kimironko", "Remera", "Gisozi", "Kimihurura", "Nyamirambo", "Kicukiro", "Gikondo",
           "Kanombe", "Niboye", "Kinyinya", "Rwezamenyo")


def demo_meter(hid: str) -> str:
    """The meter number shown for a demo history id: DEMO-MTR-009 -> KGL-20009."""
    return f"KGL-{20000 + int(hid[-3:])}"


def demo_serial(hid: str) -> str:
    return f"ITR24{int(hid[-3:]):06d}"


def demo_sector(hid: str) -> str:
    return "Kacyiru" if hid in DEMO_GPS else SECTORS[int(hid[-3:]) % len(SECTORS)]


def demo_customer(hid: str) -> str:
    return hid.replace("MTR", "CUST")  # DEMO-CUST-009: the DEMO- marker


def demo_phone(hid: str, households: int) -> str:
    n = int(hid[-3:])
    if households >= 2 and n == households:
        n -= 1  # the last two meters share a number
    return f"+250700000{n:03d}"


def set_phone(meter_id: str, raw_phone: str) -> None:
    from app.utils.phone import normalize_phone
    from app.db.session import SessionLocal
    from app.models import Customer

    phone = normalize_phone(raw_phone)
    if not phone:
        sys.exit("Use a demo meter and a Rwandan mobile number, e.g. --set-phone KGL-20001 0788123456")
    db = SessionLocal()
    try:
        customer = db.query(Customer).filter(Customer.meter_id == meter_id).first()
        if not customer or not customer.customer_id.startswith("DEMO-"):
            sys.exit(f"No DEMO household with meter {meter_id}.")
        customer.phone = phone
        db.commit()
    finally:
        db.close()
    print(f"{meter_id} now signs in with that number. --update-contacts puts the demo numbers back.")


def update_contacts(histories) -> int:
    """Set the sign-in phone and location of DEMO- rows already in the database. Touches nothing else."""
    from app.db.session import SessionLocal
    from app.models import Customer, Meter

    db = SessionLocal()
    updated = 0
    try:
        for hid in histories:
            if not hid.startswith("DEMO-"):
                continue
            customer = db.get(Customer, demo_customer(hid))
            meter = db.get(Meter, customer.meter_id) if customer else None
            if not meter:
                continue
            customer.phone = demo_phone(hid, len(histories))
            meter.gps_lat, meter.gps_lng = DEMO_GPS.get(hid, (None, None))
            updated += 1
        db.commit()
    finally:
        db.close()
    return updated


def rename_meters(histories, dry_run: bool = False) -> int:
    """Give DEMO households already in the database their new meter numbers (DEMO-MTR-009 ->
    KGL-20009), with a serial number and a Kigali sector. Their readings and flags move with
    them; past entries in the activity log keep the old number. Runs in one transaction."""
    from app.db.init_db import add_late_columns
    from app.db.session import SessionLocal
    from app.models import AnomalyFlag, Customer, Meter, Reading

    add_late_columns()
    db = SessionLocal()
    renamed = 0
    try:
        for hid in histories:
            customer = db.get(Customer, demo_customer(hid))
            old = db.get(Meter, hid)
            new_id = demo_meter(hid)
            if not customer or not old or customer.meter_id != hid or db.get(Meter, new_id):
                continue
            db.add(Meter(meter_id=new_id, customer_id=customer.customer_id, meter_type=old.meter_type,
                         last_reading=old.last_reading, last_reading_date=old.last_reading_date,
                         cover_condition=old.cover_condition, gps_lat=old.gps_lat, gps_lng=old.gps_lng,
                         serial_number=demo_serial(hid)))
            db.flush()
            db.query(Reading).filter(Reading.meter_id == hid).update({"meter_id": new_id}, synchronize_session=False)
            db.query(AnomalyFlag).filter(AnomalyFlag.household_id == hid).update(
                {"household_id": new_id}, synchronize_session=False)
            customer.meter_id = new_id
            if customer.sector == "DEMO":
                customer.sector = demo_sector(hid)
            db.flush()
            db.delete(old)
            db.flush()
            print(f"  {hid} -> {new_id}")
            renamed += 1
        if dry_run:
            db.rollback()
        else:
            db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    return renamed


def write_csv(histories, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["household_id", "reading_date", "reading_m3", "is_demo"])
        for hid, points in histories.items():
            for p in points:
                w.writerow([hid, p.date.isoformat(), f"{p.reading_m3:.3f}", "true"])


def load_into_db(histories) -> int:
    from app.db.session import Base, SessionLocal, engine
    from app.models import Customer, Meter, Reading
    import app.models  # noqa: F401  registers anomaly_flags

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    added = 0
    try:
        for hid, points in histories.items():
            customer_id, meter_id = demo_customer(hid), demo_meter(hid)
            if db.get(Customer, customer_id) or db.get(Meter, meter_id):
                continue
            # meters and customers reference each other, so link them after both rows exist.
            lat, lng = DEMO_GPS.get(hid, (None, None))
            meter = Meter(meter_id=meter_id, last_reading=points[-1].reading_m3, last_reading_date=points[-1].date,
                          gps_lat=lat, gps_lng=lng, serial_number=demo_serial(hid))
            db.add(meter)
            db.flush()
            db.add(Customer(customer_id=customer_id, name=f"DEMO Household {hid[-3:]}",
                            phone=demo_phone(hid, len(histories)), meter_id=meter_id, sector=demo_sector(hid)))
            db.flush()
            meter.customer_id = customer_id
            prev = None
            for p in points:
                db.add(Reading(meter_id=meter_id, submitted_value=p.reading_m3,
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
    parser.add_argument("--set-phone", nargs=2, metavar=("METER", "PHONE"),
                        help="Give one DEMO- household this phone number (to test SMS sign-in on your phone)")
    parser.add_argument("--update-contacts", action="store_true",
                        help="Set sign-in phones and locations on DEMO- rows already in DATABASE_URL")
    parser.add_argument("--rename-meters", action="store_true",
                        help="Give DEMO households in DATABASE_URL their KGL- meter numbers")
    parser.add_argument("--dry-run", action="store_true", help="With --rename-meters: show, change nothing")
    args = parser.parse_args()

    if args.set_phone:
        set_phone(*args.set_phone)
        return
    print(DEMO_BANNER)
    histories = generate_demo_histories(args.households, args.readings, args.seed)
    if args.rename_meters:
        n = rename_meters(histories, dry_run=args.dry_run)
        print(f"{'Would rename' if args.dry_run else 'Renamed'} {n} DEMO meters.")
        return
    write_csv(histories, args.out)
    print(f"Wrote {len(histories)} DEMO households x {args.readings} readings to {args.out}")
    if args.load_db:
        print(f"Inserted {load_into_db(histories)} DEMO households into the database (existing ones skipped).")
    if args.update_contacts:
        print(f"Updated the phone and location of {update_contacts(histories)} DEMO households.")


if __name__ == "__main__":
    main()
