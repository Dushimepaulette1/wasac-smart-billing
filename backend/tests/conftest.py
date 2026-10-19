"""Fixtures shared by every test (a fresh database, signed-in clients, demo data, fake vision models).
Helpers that tests import directly are in tests/support/."""
import dataclasses

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  registers every table on Base before create_all
from app.anomaly.config import AnomalyConfig
from app.anomaly.demo_data import generate_demo_histories
from app.anomaly.model import AnomalyModel, build_training_matrix, clear_model_cache
from app.db.session import Base
from app.vision.config import GuidanceConfig
from app.vision.models import get_registry
from support.clients import _test_client
from support.factories import add_officer, household_token
from support.vision_fakes import registry


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


@pytest.fixture
def cfg():
    # BLURRY is off in the shipped config (calibration); give it a value so its logic is still tested.
    return dataclasses.replace(GuidanceConfig.load(quality_threshold=0.4289516615867615),
                               blurry_max_laplacian_var=80.0)


@pytest.fixture
def photo_client(client, cfg):
    """Signed in (the photo endpoints need a household or staff sign-in)."""
    from app.main import app as fastapi_app

    holder = {"reg": registry(cfg)}
    fastapi_app.dependency_overrides[get_registry] = lambda: holder["reg"]
    yield client, holder
