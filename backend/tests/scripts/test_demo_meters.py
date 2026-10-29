"""Demo households: ordinary-looking meter numbers, still marked DEMO- (scripts/demo/generate_demo_households.py)."""
import pytest

from app.models import AnomalyFlag, Customer, Meter, Reading
from support.factories import add_household, make_history


@pytest.fixture
def same_db(db, monkeypatch):
    import app.db.init_db as init_db
    import app.db.session as session

    monkeypatch.setattr(session, "SessionLocal", lambda: db)
    monkeypatch.setattr(init_db, "engine", db.get_bind())
    monkeypatch.setattr(db, "close", lambda: None)
    return db


def test_when_renaming_demo_meters_should_move_readings_and_flags_to_the_new_number(same_db):
    from scripts.demo import generate_demo_households as demo

    db = same_db
    add_household(db, "DEMO-MTR-009", make_history([0.4] * 3))
    db.get(Customer, "DEMO-CUST-009").sector = "DEMO"
    db.add(AnomalyFlag(household_id="DEMO-MTR-009", anomaly_type="rule", anomaly_score=0.9))
    db.commit()
    readings = db.query(Reading).filter(Reading.meter_id == "DEMO-MTR-009").count()

    assert demo.rename_meters({"DEMO-MTR-009": []}) == 1
    customer = db.get(Customer, "DEMO-CUST-009")
    assert customer.meter_id == "KGL-20009" and customer.sector != "DEMO"
    assert db.get(Meter, "DEMO-MTR-009") is None and db.get(Meter, "KGL-20009").serial_number == "ITR24000009"
    assert db.query(Reading).filter(Reading.meter_id == "KGL-20009").count() == readings > 0
    assert db.query(AnomalyFlag).one().household_id == "KGL-20009"
    assert demo.rename_meters({"DEMO-MTR-009": []}) == 0  # safe to run again


def test_when_reading_training_data_should_leave_out_demo_households_whatever_their_meter_number(same_db):
    from scripts import _data

    add_household(same_db, "DEMO-MTR-009", make_history([0.4] * 3))
    add_household(same_db, "MTR-REAL", make_history([0.4] * 3))
    from scripts.demo import generate_demo_households as demo
    demo.rename_meters({"DEMO-MTR-009": []})

    assert set(_data.load_histories_db()) == {"MTR-REAL"}
