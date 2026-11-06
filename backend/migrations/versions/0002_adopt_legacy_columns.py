"""Bring pre-migration databases up to the baseline without changing financial records.

Revision: 0002
Previous: 0001
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    additions = (
        ("meters", "serial_number", sa.String(40)),
        ("bills", "tariff_version", sa.String(40)),
        ("readings", "corrected_value_m3", sa.Float()),
        ("payments", "reviewed_by", sa.String(64)),
        ("payments", "reviewed_at", sa.DateTime()),
        ("anomaly_flags", "decision_code", sa.String(16)),
    )
    for table, column, kind in additions:
        if column not in {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}:
            op.add_column(table, sa.Column(column, kind, nullable=True))


def downgrade():
    raise RuntimeError("Legacy adoption is additive. Restore a verified backup for rollback.")
