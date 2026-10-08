import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from sqlalchemy import (
    create_engine, Column, String, Float, DateTime, ForeignKey, Integer, text
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://wasac_user:wasac_pass@localhost:5432/wasac_db")

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Customer(Base):
    __tablename__ = "customers"

    customer_id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    email = Column(String)
    meter_id = Column(String, ForeignKey("meters.meter_id"))
    sector = Column(String)
    gps_lat = Column(Float)
    gps_lng = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

    meter = relationship("Meter", foreign_keys=[meter_id])
    bills = relationship("Bill", back_populates="customer")


class Meter(Base):
    __tablename__ = "meters"

    meter_id = Column(String, primary_key=True, index=True)
    customer_id = Column(String, ForeignKey("customers.customer_id"))
    meter_type = Column(String, default="Itron Flodis")
    last_reading = Column(Float, default=0.0)
    last_reading_date = Column(DateTime, default=datetime.utcnow)
    cover_condition = Column(String, default="clean")
    gps_lat = Column(Float)
    gps_lng = Column(Float)

    customer = relationship("Customer", foreign_keys=[customer_id])
    readings = relationship("Reading", back_populates="meter")


class Reading(Base):
    __tablename__ = "readings"

    reading_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    meter_id = Column(String, ForeignKey("meters.meter_id"))
    submitted_value = Column(Float, nullable=False)
    implied_consumption = Column(Float)
    submission_method = Column(String, default="camera")  # "camera" or "ussd"
    crnn_confidence = Column(Float)
    quality_gate_score = Column(Float)
    anomaly_score = Column(Float)
    validation_status = Column(String, default="valid")
    submission_time = Column(DateTime, default=datetime.utcnow)

    meter = relationship("Meter", back_populates="readings")
    bill = relationship("Bill", back_populates="reading", uselist=False)


class Bill(Base):
    __tablename__ = "bills"

    bill_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    customer_id = Column(String, ForeignKey("customers.customer_id"))
    reading_id = Column(Integer, ForeignKey("readings.reading_id"))
    consumption_m3 = Column(Float)
    tier1_units = Column(Float, default=0.0)
    tier2_units = Column(Float, default=0.0)
    tier3_units = Column(Float, default=0.0)
    tier4_units = Column(Float, default=0.0)
    tier1_amount = Column(Float, default=0.0)
    tier2_amount = Column(Float, default=0.0)
    tier3_amount = Column(Float, default=0.0)
    tier4_amount = Column(Float, default=0.0)
    service_charge = Column(Float, default=1000.0)
    amount_due = Column(Float)
    payment_status = Column(String, default="unpaid")
    created_at = Column(DateTime, default=datetime.utcnow)

    customer = relationship("Customer", back_populates="bills")
    reading = relationship("Reading", back_populates="bill")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
    seed_data()


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
                prev_val = reading_val
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

                bill_breakdown = _calculate_bill(consumption)
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


def _calculate_bill(consumption: float) -> dict:
    """WASAC tiered tariff calculation."""
    remaining = consumption
    t1 = min(remaining, 5)
    remaining -= t1
    t2 = min(remaining, 10)
    remaining -= t2
    t3 = min(remaining, 15)
    remaining -= t3
    t4 = max(remaining, 0)

    a1 = t1 * 350
    a2 = t2 * 530
    a3 = t3 * 791
    a4 = t4 * 1000
    service = 1000.0

    return {
        "tier1_units": t1, "tier2_units": t2, "tier3_units": t3, "tier4_units": t4,
        "tier1_amount": a1, "tier2_amount": a2, "tier3_amount": a3, "tier4_amount": a4,
        "service_charge": service,
        "total": a1 + a2 + a3 + a4 + service,
    }
