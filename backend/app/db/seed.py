"""Three sample customers with six months of history, for local development only.
Deployments set SEED_SAMPLE_DATA=0; their DEMO- households come from
scripts/demo/generate_demo_households.py instead."""
from datetime import datetime, timedelta

from app.db.session import SessionLocal
from app.models import Bill, Customer, Meter, Reading
from app.services.billing import calculate_bill


def seed_data():
    db = SessionLocal()
    try:
        # Skip seeding if data already exists
        if db.query(Customer).count() > 0:
            return

        now = datetime.utcnow()
        base_date = now - timedelta(days=180)

        customers_data = [
            {
                "customer_id": "CUST001",
                "name": "Uwimana Jean Pierre",
                "phone": "+250788123456",
                "email": "jp.uwimana@email.rw",
                "meter_id": "MTR001",
                "sector": "Kacyiru",
                "gps_lat": -1.9441,
                "gps_lng": 30.0619,
                "meter_reading": 464.0,
                "avg_consumption": 20.0,
            },
            {
                "customer_id": "CUST002",
                "name": "Mukamana Diane",
                "phone": "+250788234567",
                "email": "d.mukamana@email.rw",
                "meter_id": "MTR002",
                "sector": "Kimironko",
                "gps_lat": -1.9355,
                "gps_lng": 30.1003,
                "meter_reading": 388.0,
                "avg_consumption": 18.0,
            },
            {
                "customer_id": "CUST003",
                "name": "Habimana Patrick",
                "phone": "+250788345678",
                "email": "p.habimana@email.rw",
                "meter_id": "MTR003",
                "sector": "Nyarugenge",
                "gps_lat": -1.9500,
                "gps_lng": 30.0588,
                "meter_reading": 512.0,
                "avg_consumption": 22.0,
            },
        ]

        for c in customers_data:
            meter = Meter(
                meter_id=c["meter_id"],
                customer_id=c["customer_id"],
                meter_type="Itron Flodis",
                last_reading=c["meter_reading"],
                last_reading_date=now - timedelta(days=30),
                cover_condition="clean",
                gps_lat=c["gps_lat"],
                gps_lng=c["gps_lng"],
            )
            db.add(meter)

            customer = Customer(
                customer_id=c["customer_id"],
                name=c["name"],
                phone=c["phone"],
                email=c["email"],
                meter_id=c["meter_id"],
                sector=c["sector"],
                gps_lat=c["gps_lat"],
                gps_lng=c["gps_lng"],
                created_at=base_date,
            )
            db.add(customer)

            # 6 months of historical readings
            reading_val = c["meter_reading"] - (6 * c["avg_consumption"])
            for month in range(6):
                reading_date = base_date + timedelta(days=30 * month)
                consumption = c["avg_consumption"] + (month % 3 - 1) * 2
                reading_val += consumption

                reading = Reading(
                    meter_id=c["meter_id"],
                    submitted_value=round(reading_val, 1),
                    implied_consumption=round(consumption, 1),
                    submission_method="ussd",
                    crnn_confidence=None,
                    quality_gate_score=None,
                    anomaly_score=0.1,
                    validation_status="valid",
                    submission_time=reading_date,
                )
                db.add(reading)
                db.flush()

                bill_breakdown = calculate_bill(consumption)
                bill = Bill(
                    customer_id=c["customer_id"],
                    reading_id=reading.reading_id,
                    consumption_m3=round(consumption, 1),
                    **{k: v for k, v in bill_breakdown.items() if k != "total"},
                    amount_due=bill_breakdown["total"],
                    payment_status="paid",
                    created_at=reading_date,
                )
                db.add(bill)

        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Seed error: {e}")
    finally:
        db.close()
