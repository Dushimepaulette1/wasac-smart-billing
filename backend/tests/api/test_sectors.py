"""GET /api/sectors: the staff sector view (app/services/sectors.py)."""
from datetime import datetime, timedelta

from app.models import AnomalyFlag, Bill, Customer, Reading
from app.services.balance import balances
from support.factories import add_household, make_history

START = datetime.utcnow() - timedelta(days=150)


def household(db, meter_id, sector, phone, dailies=(0.4,) * 4):
    customer_id = add_household(db, meter_id, make_history(list(dailies), start=START), phone=phone)
    db.query(Customer).filter(Customer.customer_id == customer_id).update({"sector": sector})
    db.commit()
    return customer_id


def test_sectors_with_held_readings_or_leaks_should_come_first(db, client):
    household(db, "MTR-A1", "Remera", "+250788000201")
    household(db, "MTR-A2", "Remera", "+250788000202")
    leak = household(db, "MTR-B1", "Kacyiru", "+250788000203", dailies=(0.4, 0.4, 0.4, 0.8))
    held = household(db, "MTR-C1", "Gisozi", "+250788000204")
    db.add(Reading(meter_id="MTR-C1", submitted_value=999.0, submission_time=datetime.utcnow(),
                   validation_status="pending_review"))
    db.commit()

    body = client.get("/api/sectors").json()
    assert [s["sector"] for s in body] == ["Gisozi", "Kacyiru", "Remera"]
    gisozi, kacyiru, remera = body
    assert gisozi["held_readings"] == 1 and gisozi["attention"][0]["customer_id"] == held
    assert kacyiru["possible_leaks"] == 1 and kacyiru["attention"][0]["customer_id"] == leak
    assert remera["households"] == 2 and remera["attention"] == []
    assert remera["usual_monthly_m3"] == 12.0


def test_an_open_high_use_flag_should_count_as_a_possible_leak(db, client):
    household(db, "MTR-A1", "Remera", "+250788000201")
    db.add(AnomalyFlag(household_id="MTR-A1", anomaly_type="SPIKE", status="open"))
    db.commit()
    assert client.get("/api/sectors").json()[0]["possible_leaks"] == 1


def test_money_owed_should_match_the_balance(db, client):
    customer_id = household(db, "MTR-A1", "Remera", "+250788000201")
    reading = db.query(Reading).filter(Reading.meter_id == "MTR-A1").order_by(Reading.reading_id.desc()).first()
    db.add(Bill(customer_id=customer_id, reading_id=reading.reading_id, consumption_m3=12, amount_due=8590.0,
                payment_status="unpaid", created_at=datetime.utcnow()))
    db.commit()
    owed = sum(b.outstanding for b in balances(db, customer_id).values() if not b.settled)
    assert client.get("/api/sectors").json()[0]["owed"] == owed == 8590.0


def test_households_and_signed_out_callers_should_be_refused(db, household_client, anon_client):
    household(db, "MTR-A1", "Remera", "+250788000111")
    assert household_client.get("/api/sectors").status_code in (401, 403)
    assert anon_client.get("/api/sectors").status_code == 401
