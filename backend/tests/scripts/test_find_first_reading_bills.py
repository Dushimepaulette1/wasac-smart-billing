"""scripts/find_first_reading_bills.py: bills that charged a whole meter register (read-only)."""
from datetime import datetime, timedelta

from app.models import Bill, Customer, Meter, Reading
from app.services.billing import build_bill
from scripts.find_first_reading_bills import find
from support.factories import add_household, make_history


def test_when_a_first_reading_was_billed_from_zero_should_list_it_and_nothing_else(db):
    # The old behaviour: a meter added with last_reading 0, its first reading billed in full.
    db.add(Meter(meter_id="MTR-Z", last_reading=0.0))
    db.add(Customer(customer_id="CUST-Z", name="Z", phone="+250788000222", meter_id="MTR-Z"))
    db.flush()
    first = Reading(meter_id="MTR-Z", submitted_value=431.46, implied_consumption=431.46,
                    validation_status="valid", submission_time=datetime.utcnow())
    db.add(first)
    db.flush()
    db.add(build_bill("CUST-Z", first.reading_id, 431.46))
    # An ordinary household: its bill is measured from the previous reading.
    points = make_history([0.4] * 3, start=datetime.utcnow() - timedelta(days=120))
    add_household(db, "MTR-OK", points)
    ok = Reading(meter_id="MTR-OK", submitted_value=points[-1].reading_m3 + 12, validation_status="valid",
                 submission_time=datetime.utcnow())
    db.add(ok)
    db.flush()
    db.add(build_bill("CUST-OK", ok.reading_id, 12.0))
    db.commit()
    before = (db.query(Bill).count(), db.query(Reading).count())

    found = find(db)
    assert [(b.customer_id, r.meter_id) for b, r, _ in found] == [("CUST-Z", "MTR-Z")]
    assert (db.query(Bill).count(), db.query(Reading).count()) == before
    assert not db.new and not db.dirty
