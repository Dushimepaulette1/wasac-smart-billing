"""Create the database tables at start-up (and the local sample data unless SEED_SAMPLE_DATA=0).

create_all() only creates tables that do not exist yet; it never changes an existing table, so a
new column on an old table needs a migration. That is why newer features got new tables.
"""
import app.models  # noqa: F401  registers every table on Base before create_all
from app.core.config import seed_sample_data
from app.db import seed
from app.db.session import Base, engine


def init_db():
    Base.metadata.create_all(bind=engine)
    # The three sample customers are for local development. Deployments set SEED_SAMPLE_DATA=0
    # and load clearly marked DEMO- households with scripts/demo/generate_demo_households.py.
    if seed_sample_data():
        seed.seed_data()
