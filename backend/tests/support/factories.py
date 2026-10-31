"""Make test data: readings histories, households, staff accounts, household tokens."""
from datetime import datetime, timedelta

from app.anomaly.features import ReadingPoint
from app.models import Customer, Meter, Reading


T0 = datetime(2025, 1, 1, 9, 0)


def make_history(dailies, days=30, start_m3=500.0, start=T0):
    """Readings whose successive periods have the given daily consumptions."""
    if isinstance(days, (int, float)):
        days = [days] * len(dailies)
    points = [ReadingPoint(start, start_m3)]
    for daily, d in zip(dailies, days):
        prev = points[-1]
        points.append(ReadingPoint(prev.date + timedelta(days=d), round(prev.reading_m3 + daily * d, 3)))
    return points


def add_household(db, meter_id, points, phone="+250788000111"):
    customer_id = meter_id.replace("MTR", "CUST")
    db.add(Meter(meter_id=meter_id, last_reading=points[-1].reading_m3, last_reading_date=points[-1].date))
    db.flush()  # the meter first: PostgreSQL checks customers.meter_id (tests/pg)
    db.add(Customer(customer_id=customer_id, name="Test", phone=phone, meter_id=meter_id, sector="Test"))
    db.flush()
    db.query(Meter).filter(Meter.meter_id == meter_id).update({"customer_id": customer_id})
    for p in points:
        db.add(Reading(meter_id=meter_id, submitted_value=p.reading_m3, submission_time=p.date))
    db.commit()
    return customer_id


def add_officer(db, username="officer1", password="correct horse", full_name="Test Officer", active=True, role="officer"):
    from app.models import StaffUser
    from app.core.security import hash_password

    user = StaffUser(
        username=username,
        full_name=full_name,
        password_hash=hash_password(password, iterations=1000),  # fast in tests
        is_active=active,
        role=role,
    )
    db.add(user)
    db.commit()
    return user


def staff_token(user):
    """A token as /auth/login gives this staff user (stamped with their current password)."""
    from app.core.security import make_staff_token

    return make_staff_token(user.username, user.password_hash)[0]


def household_token(phone="+250788000111"):
    from app.api.deps import SESSION_TTL, SUBJECT_PREFIX
    from app.core.security import make_token

    return make_token(SUBJECT_PREFIX + phone, ttl=SESSION_TTL)[0]
