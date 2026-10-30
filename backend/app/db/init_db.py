"""Create the database tables at start-up (and the local sample data unless SEED_SAMPLE_DATA=0).

create_all() only creates tables that do not exist yet; it never changes an existing table, so a
new column on an old table is added by LATE_COLUMNS below (most newer features got new tables).
"""
import logging

from sqlalchemy import inspect, text

import app.models  # noqa: F401  registers every table on Base before create_all
from app.core.config import seed_sample_data
from app.db import seed
from app.db.session import Base, engine


logger = logging.getLogger(__name__)

# Indexes added after their table existed (create_all skips existing tables). IF NOT EXISTS: safe
# to run at every start; Postgres and SQLite both accept it.
LATE_INDEXES = (
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_bills_reading_id ON bills (reading_id)",
    # Partial indexes (Postgres and SQLite both support WHERE): one open payment attempt per bill,
    # one MoMo Pay transaction ID per payment that has not failed.
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_payments_one_pending ON payments (bill_id) WHERE status = 'pending'",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_payments_momo_pay_txn ON payments (transaction_id) "
    "WHERE provider = 'momo_pay' AND status <> 'failed'",
)


# Columns added after their table existed: (table, column, SQL type). Added only when missing.
LATE_COLUMNS = (
    ("meters", "serial_number", "VARCHAR(40)"),
    ("bills", "tariff_version", "VARCHAR(40)"),
)


def add_late_columns(bind=None) -> None:
    bind = bind or engine
    for table, column, sql_type in LATE_COLUMNS:
        try:
            if column in {c["name"] for c in inspect(bind).get_columns(table)}:
                continue
            with bind.begin() as conn:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {sql_type}"))
        except Exception as e:  # the app still runs; the feature that needs the column fails loudly
            logger.error("Could not add column %s.%s: %s", table, column, type(e).__name__)


def add_late_indexes(bind=None) -> None:
    bind = bind or engine
    for statement in LATE_INDEXES:
        try:
            with bind.begin() as conn:
                conn.execute(text(statement))
        except Exception as e:  # e.g. existing duplicates: the app still runs; fix the data, restart
            logger.error("Could not add index (%s): %s", statement.split(" ON ")[0], type(e).__name__)


def init_db():
    Base.metadata.create_all(bind=engine)
    add_late_columns(engine)
    add_late_indexes(engine)
    # The three sample customers are for local development. Deployments set SEED_SAMPLE_DATA=0
    # and load clearly marked DEMO- households with scripts/demo/generate_demo_households.py.
    if seed_sample_data():
        seed.seed_data()
