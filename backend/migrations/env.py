"""Run versioned schema changes using DATABASE_URL, never a checked-in connection string."""
from alembic import context

import app.models  # noqa: F401
from app.db.session import Base, engine

config = context.config


def migrate(connection):
    if connection.dialect.name == "postgresql":
        from sqlalchemy import text
        connection.execute(text("SELECT pg_advisory_xact_lock(742619038)"))
    context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    raise RuntimeError("Use an online connection: the baseline checks existing tables before adoption.")
elif config.attributes.get("connection") is not None:
    migrate(config.attributes["connection"])
else:
    with engine.begin() as connection:
        migrate(connection)
