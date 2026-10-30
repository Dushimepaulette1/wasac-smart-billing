"""Three local test households for trying the reliability work by hand. Local SQLite only.

    DATABASE_URL=sqlite:///./local.db python scripts/demo/setup_manual_test_cases.py

0700 000 099  an old-bug first bill (431.460 m3 charged from zero)
0700 000 098  an MTN payment stuck for an hour
0700 000 097  a meter near the top of its register (send 00000.010)
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
if not os.getenv("DATABASE_URL", "").startswith("sqlite"):
    sys.exit("Refusing: this writes test data, so DATABASE_URL must be a local sqlite file.")

from datetime import datetime, timedelta
from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.models import Bill, Customer, Meter, Payment, Reading
from app.services.billing import build_bill

init_db()
db = SessionLocal()
now = datetime.utcnow()

# Old-bug household: first reading 431.460 billed from zero. Sign in with 0700 000 099.
db.add(Meter(meter_id="KGL-BUG", last_reading=431.46, last_reading_date=now - timedelta(days=40)))
db.flush()
db.add(Customer(customer_id="DEMO-BUG", name="DEMO Old Bug", phone="+250700000099", meter_id="KGL-BUG", sector="Remera"))
db.flush()
db.get(Meter, "KGL-BUG").customer_id = "DEMO-BUG"
r = Reading(meter_id="KGL-BUG", submitted_value=431.46, implied_consumption=431.46,
            validation_status="valid", submission_time=now - timedelta(days=40))
db.add(r)
db.flush()
db.add(build_bill("DEMO-BUG", r.reading_id, 431.46))

# Stuck-payment household: an MTN attempt open for an hour. Sign in with 0700 000 098.
db.add(Meter(meter_id="KGL-STUCK", last_reading=500.0, last_reading_date=now - timedelta(days=30)))
db.flush()
db.add(Customer(customer_id="DEMO-STUCK", name="DEMO Stuck Pay", phone="+250700000098", meter_id="KGL-STUCK", sector="Remera"))
db.flush()
db.get(Meter, "KGL-STUCK").customer_id = "DEMO-STUCK"
r2 = Reading(meter_id="KGL-STUCK", submitted_value=500.0, implied_consumption=12.0,
             validation_status="valid", submission_time=now - timedelta(days=30))
db.add(r2)
db.flush()
b = build_bill("DEMO-STUCK", r2.reading_id, 12.0)
db.add(b)
db.flush()
db.add(Payment(bill_id=b.bill_id, provider="momo_sandbox", reference_id="11111111-2222-4333-8444-555555555555",
               status="pending", amount=b.amount_due, currency="EUR", reason="confirming with MTN",
               created_at=now - timedelta(hours=1), updated_at=now - timedelta(hours=1)))

# Rollover household: meter near the top. Sign in with 0700 000 097; send 00000.010.
db.add(Meter(meter_id="KGL-TOP", last_reading=99950.0, last_reading_date=now - timedelta(days=30)))
db.flush()
db.add(Customer(customer_id="DEMO-TOP", name="DEMO Near Top", phone="+250700000097", meter_id="KGL-TOP", sector="Remera"))
db.flush()
db.get(Meter, "KGL-TOP").customer_id = "DEMO-TOP"
db.add(Reading(meter_id="KGL-TOP", submitted_value=99950.0, validation_status="valid",
               submission_time=now - timedelta(days=30)))
db.commit()
print("Test households added.")
