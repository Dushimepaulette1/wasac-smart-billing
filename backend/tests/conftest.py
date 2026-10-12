import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import anomaly.db_models  # noqa: E402,F401  registers anomaly_flags on Base
import auth.models  # noqa: E402,F401  registers staff_users on Base
from anomaly.config import AnomalyConfig  # noqa: E402
from anomaly.demo_data import generate_demo_histories  # noqa: E402
from anomaly.features import ReadingPoint  # noqa: E402
from anomaly.model import AnomalyModel, build_training_matrix, clear_model_cache  # noqa: E402
from database import Base, Customer, Meter, Reading  # noqa: E402

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


@pytest.fixture(autouse=True)
def isolated_model_path(tmp_path, monkeypatch):
    """No test ever touches a real model file; each starts in rules-only mode."""
    monkeypatch.setenv("ANOMALY_MODEL_PATH", str(tmp_path / "model.joblib"))
    clear_model_cache()
    yield
    clear_model_cache()


@pytest.fixture
def config():
    return AnomalyConfig.from_env()


@pytest.fixture(scope="session")
def demo_histories():
    return generate_demo_histories()


@pytest.fixture(scope="session")
def demo_model(demo_histories):
    cfg = AnomalyConfig()
    return AnomalyModel.train(build_training_matrix(demo_histories.values(), cfg), cfg)


@pytest.fixture
def trained_model_on_disk(demo_model, config):
    demo_model.save(config.model_path)
    clear_model_cache()
    return demo_model


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def add_household(db, meter_id, points, phone="+250788000111"):
    customer_id = meter_id.replace("MTR", "CUST")
    db.add(Meter(meter_id=meter_id, last_reading=points[-1].reading_m3, last_reading_date=points[-1].date))
    db.add(Customer(customer_id=customer_id, name="Test", phone=phone, meter_id=meter_id, sector="Test"))
    db.flush()
    db.query(Meter).filter(Meter.meter_id == meter_id).update({"customer_id": customer_id})
    for p in points:
        db.add(Reading(meter_id=meter_id, submitted_value=p.reading_m3, submission_time=p.date))
    db.commit()
    return customer_id


def add_officer(db, username="officer1", password="correct horse", full_name="Test Officer", active=True):
    from auth.models import StaffUser
    from auth.security import hash_password

    user = StaffUser(
        username=username,
        full_name=full_name,
        password_hash=hash_password(password, iterations=1000),  # fast in tests
        is_active=active,
    )
    db.add(user)
    db.commit()
    return user


def _test_client(db, headers=None):
    from fastapi.testclient import TestClient

    from database import get_db
    from main import app

    def override():
        yield db

    app.dependency_overrides[get_db] = override
    # no context manager: lifespan (Postgres init_db) is not run
    return app, TestClient(app, headers=headers or {})


@pytest.fixture
def client(db):
    """Signed in as an officer, as the staff dashboard is."""
    from auth.security import make_token

    add_officer(db)
    app, test_client = _test_client(db, {"Authorization": f"Bearer {make_token('officer1')[0]}"})
    try:
        yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def anon_client(db):
    """Not signed in, as the household app is."""
    from auth.routes import reset_failures

    reset_failures()
    app, test_client = _test_client(db)
    try:
        yield test_client
    finally:
        app.dependency_overrides.clear()
        reset_failures()
