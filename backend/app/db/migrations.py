"""Apply checked-in revisions before serving requests; a failed migration stops startup."""
from pathlib import Path

from alembic import command
from alembic.config import Config


def upgrade_schema(engine) -> None:
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
