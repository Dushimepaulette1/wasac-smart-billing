"""Deployment configuration and migration adoption must fail safely and preserve existing rows."""
import pytest
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text

import app.models  # noqa: F401
from app.db.migrations import upgrade_schema
from app.db.session import Base, database_url


@pytest.mark.parametrize("flag,value", [("APP_ENV", "production"), ("RENDER", "true")])
def test_production_without_a_database_should_fail_without_showing_a_connection_string(monkeypatch, flag, value):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv(flag, value)
    with pytest.raises(RuntimeError, match="DATABASE_URL must be set"):
        database_url()


def test_local_database_default_and_explicit_override(monkeypatch):
    for key in ("DATABASE_URL", "APP_ENV", "RENDER"):
        monkeypatch.delenv(key, raising=False)
    assert database_url() == "sqlite:///./local.db"
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./chosen.db")
    assert database_url() == "sqlite:///./chosen.db"


def test_new_database_should_upgrade_once_and_have_financial_guards():
    engine = create_engine("sqlite://")
    upgrade_schema(engine)
    upgrade_schema(engine)
    with engine.connect() as conn:
        assert MigrationContext.configure(conn).get_current_revision() == "0002"
    assert {"customers", "meters", "bills", "payments"} <= set(inspect(engine).get_table_names())
    assert "uq_payments_one_pending" in {i["name"] for i in inspect(engine).get_indexes("payments")}


def test_legacy_database_should_gain_missing_columns_without_changing_customers():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO customers (customer_id, name, phone) VALUES ('C', 'Demo', '0700000001')"))
        conn.execute(text("ALTER TABLE bills DROP COLUMN tariff_version"))
        conn.execute(text("ALTER TABLE meters DROP COLUMN serial_number"))
    upgrade_schema(engine)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT name FROM customers WHERE customer_id = 'C'")).scalar() == "Demo"
    assert "tariff_version" in {c["name"] for c in inspect(engine).get_columns("bills")}
    assert "serial_number" in {c["name"] for c in inspect(engine).get_columns("meters")}


def test_duplicate_legacy_bills_should_stop_migration_instead_of_losing_the_guard():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("DROP INDEX uq_bills_reading_id"))
        conn.execute(text("INSERT INTO bills (bill_id, reading_id) VALUES (1, 7), (2, 7)"))
    with pytest.raises(Exception):
        upgrade_schema(engine)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM bills")).scalar() == 2
