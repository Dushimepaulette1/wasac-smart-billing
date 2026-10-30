"""List bills that charged a meter's whole register: read-only, changes nothing.

    python scripts/find_first_reading_bills.py            uses DATABASE_URL (backend/.env)

Before the no-baseline safeguard (app/anomaly/service.py has_baseline), a household added without a
first reading had meters.last_reading 0, and its first reading was billed from 0: the bill's
consumption equals the whole meter reading. This lists those bills (no earlier confirmed reading,
consumption equal to the reading) so a supervisor can correct them with a billed-reading
correction. It opens a read-only transaction on Postgres and never commits.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.anomaly.statuses import NOT_CONFIRMED  # noqa: E402
from app.models import Bill, Customer, Reading  # noqa: E402


def find(db: Session) -> list:
    """(bill, reading, customer) for every bill measured from no starting value."""
    rows = []
    for bill, reading, customer in (
        db.query(Bill, Reading, Customer)
        .join(Reading, Reading.reading_id == Bill.reading_id)
        .outerjoin(Customer, Customer.customer_id == Bill.customer_id)
        .order_by(Bill.bill_id)
        .all()
    ):
        if reading.corrected_value_m3 is not None:  # already corrected
            continue
        if not reading.submitted_value or abs((bill.consumption_m3 or 0) - reading.submitted_value) > 0.0005:
            continue
        earlier = db.query(Reading.reading_id).filter(
            Reading.meter_id == reading.meter_id,
            Reading.submission_time < reading.submission_time,
            Reading.validation_status.notin_(NOT_CONFIRMED),
        ).first()
        if earlier is None:
            rows.append((bill, reading, customer))
    return rows


def main() -> int:
    from app.db.session import SessionLocal, engine

    db = SessionLocal()
    try:
        if engine.dialect.name == "postgresql":
            db.execute(text("SET TRANSACTION READ ONLY"))
        found = find(db)
        if not found:
            print("No bills charged a whole meter register.")
            return 0
        print("bill_id, customer_id, meter_id, reading_m3, consumption_m3, amount_due, payment_status")
        for bill, reading, customer in found:
            print(f"{bill.bill_id}, {customer.customer_id if customer else '?'}, {reading.meter_id}, "
                  f"{reading.submitted_value:.3f}, {bill.consumption_m3:.3f}, {bill.amount_due:,.2f}, {bill.payment_status}")
        print(f"{len(found)} bill(s). Correct them with a billed-reading correction; nothing was changed.")
        return 0
    finally:
        db.rollback()
        db.close()


if __name__ == "__main__":
    sys.exit(main())
