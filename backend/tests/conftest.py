import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.models  # noqa: E402,F401  registers every table on Base
from app.anomaly.config import AnomalyConfig  # noqa: E402
from app.anomaly.demo_data import generate_demo_histories  # noqa: E402
from app.anomaly.features import ReadingPoint  # noqa: E402
from app.anomaly.model import AnomalyModel, build_training_matrix, clear_model_cache  # noqa: E402
from app.db.session import Base  # noqa: E402
from app.models import Customer, Meter, Reading  # noqa: E402

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
def no_real_sms(monkeypatch):
    """app/db/session.py loads backend/.env; tests must never send a real SMS with its keys."""
    for name in ("AT_USERNAME", "AT_API_KEY", "AT_SENDER_ID"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture(autouse=True)
def fresh_rate_limits():
    """Rate limits are per process; reset them so tests do not throttle each other."""
    from app.core import ratelimit
    from app.api.routes.household_auth import reset_household_limits

    ratelimit.reset_limits()
    reset_household_limits()
    yield
    ratelimit.reset_limits()
    reset_household_limits()


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


def _test_client(db, headers=None):
    from fastapi.testclient import TestClient

    from app.db.session import get_db
    from app.main import app as fastapi_app

    def override():
        yield db

    fastapi_app.dependency_overrides[get_db] = override
    # no context manager: lifespan (Postgres init_db) is not run
    return fastapi_app, TestClient(fastapi_app, headers=headers or {})


@pytest.fixture
def client(db):
    """Signed in as an officer, as the staff dashboard is."""
    from app.core.security import make_token

    add_officer(db)
    fastapi_app, test_client = _test_client(db, {"Authorization": f"Bearer {make_token('officer1')[0]}"})
    try:
        yield test_client
    finally:
        fastapi_app.dependency_overrides.clear()


def signed_in_client(db, username):
    """A client signed in as an existing staff user; the caller clears fastapi_app.dependency_overrides."""
    from app.core.security import make_token

    return _test_client(db, {"Authorization": f"Bearer {make_token(username)[0]}"})


def household_token(phone="+250788000111"):
    from app.api.deps import SESSION_TTL, SUBJECT_PREFIX
    from app.core.security import make_token

    return make_token(SUBJECT_PREFIX + phone, ttl=SESSION_TTL)[0]


@pytest.fixture
def household_client(db):
    """Signed in as the household whose phone is +250788000111 (add_household's default)."""
    fastapi_app, test_client = _test_client(db, {"Authorization": f"Bearer {household_token()}"})
    try:
        yield test_client
    finally:
        fastapi_app.dependency_overrides.clear()


@pytest.fixture
def anon_client(db):
    """Not signed in, as the household app is."""
    from app.api.routes.staff_auth import reset_failures

    reset_failures()
    fastapi_app, test_client = _test_client(db)
    try:
        yield test_client
    finally:
        fastapi_app.dependency_overrides.clear()
        reset_failures()
