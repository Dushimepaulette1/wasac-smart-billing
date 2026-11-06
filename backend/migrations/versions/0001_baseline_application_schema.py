"""Baseline application schema

Revision: 0001
Previous: 
"""
from alembic import op
import sqlalchemy as sa


revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def _create_table(name, *columns, **kw):
    # Adopt legacy tables without replacing their rows. Revision 0002 fills known late columns.
    if not sa.inspect(op.get_bind()).has_table(name):
        op.create_table(name, *columns, **kw)


def _create_index(name, table, columns, **kw):
    existing = {i["name"] for i in sa.inspect(op.get_bind()).get_indexes(table)}
    if name not in existing:
        op.create_index(name, table, columns, **kw)


def upgrade():
    _create_table('customers',
    sa.Column('customer_id', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('phone', sa.String(), nullable=False),
    sa.Column('email', sa.String(), nullable=True),
    sa.Column('meter_id', sa.String(), nullable=True),
    sa.Column('sector', sa.String(), nullable=True),
    sa.Column('gps_lat', sa.Float(), nullable=True),
    sa.Column('gps_lng', sa.Float(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    *([sa.ForeignKeyConstraint(['meter_id'], ['meters.meter_id'])]
      if op.get_bind().dialect.name == 'sqlite' else []),
    sa.PrimaryKeyConstraint('customer_id')
    )
    _create_index(op.f('ix_customers_customer_id'), 'customers', ['customer_id'], unique=False)
    _create_table('household_codes',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('phone', sa.String(length=20), nullable=False),
    sa.Column('code_hash', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('expires_at', sa.DateTime(), nullable=False),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('used_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    _create_index(op.f('ix_household_codes_created_at'), 'household_codes', ['created_at'], unique=False)
    _create_index(op.f('ix_household_codes_phone'), 'household_codes', ['phone'], unique=False)
    _create_table('meters',
    sa.Column('meter_id', sa.String(), nullable=False),
    sa.Column('customer_id', sa.String(), nullable=True),
    sa.Column('meter_type', sa.String(), nullable=True),
    sa.Column('last_reading', sa.Float(), nullable=True),
    sa.Column('last_reading_date', sa.DateTime(), nullable=True),
    sa.Column('cover_condition', sa.String(), nullable=True),
    sa.Column('gps_lat', sa.Float(), nullable=True),
    sa.Column('gps_lng', sa.Float(), nullable=True),
    sa.Column('serial_number', sa.String(length=40), nullable=True),
    sa.ForeignKeyConstraint(['customer_id'], ['customers.customer_id'], ),
    sa.PrimaryKeyConstraint('meter_id')
    )
    _create_index(op.f('ix_meters_meter_id'), 'meters', ['meter_id'], unique=False)
    _create_table('payment_statement_entries',
    sa.Column('transaction_id', sa.String(length=64), nullable=False),
    sa.Column('amount', sa.Float(), nullable=False),
    sa.Column('reference', sa.String(length=64), nullable=True),
    sa.Column('uploaded_by', sa.String(), nullable=False),
    sa.Column('uploaded_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('transaction_id')
    )
    _create_table('push_subscriptions',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('phone', sa.String(length=20), nullable=False),
    sa.Column('endpoint', sa.String(length=1024), nullable=False),
    sa.Column('p256dh', sa.String(length=200), nullable=False),
    sa.Column('auth', sa.String(length=100), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('last_sent_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('endpoint')
    )
    _create_index(op.f('ix_push_subscriptions_phone'), 'push_subscriptions', ['phone'], unique=False)
    _create_table('sms_outbox',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('at', sa.DateTime(), nullable=False),
    sa.Column('phone', sa.String(length=20), nullable=False),
    sa.Column('message', sa.String(length=480), nullable=False),
    sa.Column('status', sa.String(length=40), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    _create_index(op.f('ix_sms_outbox_at'), 'sms_outbox', ['at'], unique=False)
    _create_table('staff_actions',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('at', sa.DateTime(), nullable=False),
    sa.Column('username', sa.String(length=64), nullable=False),
    sa.Column('action', sa.String(length=32), nullable=False),
    sa.Column('target', sa.String(length=64), nullable=True),
    sa.Column('detail', sa.String(length=200), nullable=True),
    sa.Column('ip', sa.String(length=64), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    _create_index(op.f('ix_staff_actions_at'), 'staff_actions', ['at'], unique=False)
    _create_index(op.f('ix_staff_actions_username'), 'staff_actions', ['username'], unique=False)
    _create_table('staff_users',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('username', sa.String(), nullable=False),
    sa.Column('full_name', sa.String(), nullable=False),
    sa.Column('password_hash', sa.String(), nullable=False),
    sa.Column('role', sa.String(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    _create_index(op.f('ix_staff_users_username'), 'staff_users', ['username'], unique=True)
    _create_table('meter_corrections',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('meter_id', sa.String(), nullable=False),
    sa.Column('customer_id', sa.String(), nullable=False),
    sa.Column('current_m3', sa.Float(), nullable=False),
    sa.Column('reading_m3', sa.Float(), nullable=False),
    sa.Column('reason', sa.String(length=200), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('requested_by', sa.String(), nullable=False),
    sa.Column('requested_at', sa.DateTime(), nullable=False),
    sa.Column('decided_by', sa.String(), nullable=True),
    sa.Column('decided_at', sa.DateTime(), nullable=True),
    sa.Column('decision_reason', sa.String(length=200), nullable=True),
    sa.ForeignKeyConstraint(['customer_id'], ['customers.customer_id'], ),
    sa.ForeignKeyConstraint(['meter_id'], ['meters.meter_id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    _create_index(op.f('ix_meter_corrections_meter_id'), 'meter_corrections', ['meter_id'], unique=False)
    _create_index('uq_meter_corrections_awaiting', 'meter_corrections', ['meter_id'], unique=True, sqlite_where=sa.text("status = 'awaiting_approval'"), postgresql_where=sa.text("status = 'awaiting_approval'"))
    _create_table('readings',
    sa.Column('reading_id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('meter_id', sa.String(), nullable=True),
    sa.Column('submitted_value', sa.Float(), nullable=False),
    sa.Column('corrected_value_m3', sa.Float(), nullable=True),
    sa.Column('implied_consumption', sa.Float(), nullable=True),
    sa.Column('submission_method', sa.String(), nullable=True),
    sa.Column('crnn_confidence', sa.Float(), nullable=True),
    sa.Column('quality_gate_score', sa.Float(), nullable=True),
    sa.Column('anomaly_score', sa.Float(), nullable=True),
    sa.Column('validation_status', sa.String(), nullable=True),
    sa.Column('submission_time', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['meter_id'], ['meters.meter_id'], ),
    sa.PrimaryKeyConstraint('reading_id')
    )
    _create_index(op.f('ix_readings_reading_id'), 'readings', ['reading_id'], unique=False)
    _create_table('staff_temporary_passwords',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('issued_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['staff_users.id'], ),
    sa.PrimaryKeyConstraint('user_id')
    )
    _create_table('anomaly_flags',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('household_id', sa.String(), nullable=False),
    sa.Column('reading_id', sa.Integer(), nullable=True),
    sa.Column('anomaly_type', sa.String(), nullable=False),
    sa.Column('anomaly_score', sa.Float(), nullable=True),
    sa.Column('features', sa.JSON(), nullable=True),
    sa.Column('requires_staff_review', sa.Boolean(), nullable=False),
    sa.Column('message_for_household', sa.String(), nullable=True),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('resolved_at', sa.DateTime(), nullable=True),
    sa.Column('decision_code', sa.String(length=16), nullable=True),
    sa.ForeignKeyConstraint(['household_id'], ['meters.meter_id'], ),
    sa.ForeignKeyConstraint(['reading_id'], ['readings.reading_id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    _create_index(op.f('ix_anomaly_flags_anomaly_type'), 'anomaly_flags', ['anomaly_type'], unique=False)
    _create_index(op.f('ix_anomaly_flags_household_id'), 'anomaly_flags', ['household_id'], unique=False)
    _create_index(op.f('ix_anomaly_flags_id'), 'anomaly_flags', ['id'], unique=False)
    _create_index(op.f('ix_anomaly_flags_status'), 'anomaly_flags', ['status'], unique=False)
    _create_table('bill_corrections',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('customer_id', sa.String(), nullable=False),
    sa.Column('reading_id', sa.Integer(), nullable=False),
    sa.Column('value_before_m3', sa.Float(), nullable=False),
    sa.Column('corrected_value_m3', sa.Float(), nullable=False),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('start_m3', sa.Float(), nullable=True),
    sa.Column('reason', sa.String(length=200), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('requested_by', sa.String(length=64), nullable=False),
    sa.Column('decided_by', sa.String(length=64), nullable=True),
    sa.Column('decision_reason', sa.String(length=200), nullable=True),
    sa.Column('request_key', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('decided_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['customer_id'], ['customers.customer_id'], ),
    sa.ForeignKeyConstraint(['reading_id'], ['readings.reading_id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('request_key')
    )
    _create_index(op.f('ix_bill_corrections_customer_id'), 'bill_corrections', ['customer_id'], unique=False)
    _create_index(op.f('ix_bill_corrections_reading_id'), 'bill_corrections', ['reading_id'], unique=False)
    _create_index(op.f('ix_bill_corrections_status'), 'bill_corrections', ['status'], unique=False)
    _create_table('bills',
    sa.Column('bill_id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('customer_id', sa.String(), nullable=True),
    sa.Column('reading_id', sa.Integer(), nullable=True),
    sa.Column('consumption_m3', sa.Float(), nullable=True),
    sa.Column('tier1_units', sa.Float(), nullable=True),
    sa.Column('tier2_units', sa.Float(), nullable=True),
    sa.Column('tier3_units', sa.Float(), nullable=True),
    sa.Column('tier4_units', sa.Float(), nullable=True),
    sa.Column('tier1_amount', sa.Float(), nullable=True),
    sa.Column('tier2_amount', sa.Float(), nullable=True),
    sa.Column('tier3_amount', sa.Float(), nullable=True),
    sa.Column('tier4_amount', sa.Float(), nullable=True),
    sa.Column('service_charge', sa.Float(), nullable=True),
    sa.Column('amount_due', sa.Float(), nullable=True),
    sa.Column('payment_status', sa.String(), nullable=True),
    sa.Column('tariff_version', sa.String(length=40), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['customer_id'], ['customers.customer_id'], ),
    sa.ForeignKeyConstraint(['reading_id'], ['readings.reading_id'], ),
    sa.PrimaryKeyConstraint('bill_id')
    )
    _create_index(op.f('ix_bills_bill_id'), 'bills', ['bill_id'], unique=False)
    _create_index('uq_bills_reading_id', 'bills', ['reading_id'], unique=True)
    _create_table('photo_reads',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('owner', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('image_jpeg', sa.LargeBinary(), nullable=True),
    sa.Column('reader_digits', sa.String(length=16), nullable=True),
    sa.Column('confidence_min', sa.Float(), nullable=True),
    sa.Column('confidence_mean', sa.Float(), nullable=True),
    sa.Column('quality_score', sa.Float(), nullable=True),
    sa.Column('crop_method', sa.String(length=16), nullable=True),
    sa.Column('guidance', sa.String(length=200), nullable=True),
    sa.Column('models', sa.String(length=200), nullable=True),
    sa.Column('reading_id', sa.Integer(), nullable=True),
    sa.Column('edited', sa.Boolean(), nullable=True),
    sa.ForeignKeyConstraint(['reading_id'], ['readings.reading_id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('reading_id')
    )
    _create_index(op.f('ix_photo_reads_created_at'), 'photo_reads', ['created_at'], unique=False)
    _create_table('reading_evidence',
    sa.Column('reading_id', sa.Integer(), nullable=False),
    sa.Column('photo_source', sa.String(length=16), nullable=False),
    sa.Column('lat', sa.Float(), nullable=True),
    sa.Column('lng', sa.Float(), nullable=True),
    sa.Column('accuracy_m', sa.Float(), nullable=True),
    sa.Column('distance_m', sa.Float(), nullable=True),
    sa.Column('outcome', sa.String(length=16), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['reading_id'], ['readings.reading_id'], ),
    sa.PrimaryKeyConstraint('reading_id')
    )
    _create_table('account_credits',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('customer_id', sa.String(), nullable=False),
    sa.Column('amount', sa.Float(), nullable=False),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('source_bill_id', sa.Integer(), nullable=True),
    sa.Column('bill_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['bill_id'], ['bills.bill_id'], ),
    sa.ForeignKeyConstraint(['customer_id'], ['customers.customer_id'], ),
    sa.ForeignKeyConstraint(['source_bill_id'], ['bills.bill_id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    _create_index(op.f('ix_account_credits_customer_id'), 'account_credits', ['customer_id'], unique=False)
    _create_table('bill_adjustments',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('correction_id', sa.Integer(), nullable=False),
    sa.Column('bill_id', sa.Integer(), nullable=False),
    sa.Column('consumption_before', sa.Float(), nullable=False),
    sa.Column('consumption_after', sa.Float(), nullable=False),
    sa.Column('amount_before', sa.Float(), nullable=False),
    sa.Column('amount_after', sa.Float(), nullable=False),
    sa.Column('amount_delta', sa.Float(), nullable=False),
    sa.Column('tiers', sa.JSON(), nullable=True),
    sa.Column('tariff_version', sa.String(length=40), nullable=False),
    sa.ForeignKeyConstraint(['bill_id'], ['bills.bill_id'], ),
    sa.ForeignKeyConstraint(['correction_id'], ['bill_corrections.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    _create_index(op.f('ix_bill_adjustments_bill_id'), 'bill_adjustments', ['bill_id'], unique=False)
    _create_index(op.f('ix_bill_adjustments_correction_id'), 'bill_adjustments', ['correction_id'], unique=False)
    _create_index('uq_bill_adjustment', 'bill_adjustments', ['correction_id', 'bill_id'], unique=True)
    _create_table('message_dismissals',
    sa.Column('flag_id', sa.Integer(), nullable=False),
    sa.Column('dismissed_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['flag_id'], ['anomaly_flags.id'], ),
    sa.PrimaryKeyConstraint('flag_id')
    )
    _create_table('payments',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('bill_id', sa.Integer(), nullable=False),
    sa.Column('provider', sa.String(length=20), nullable=False),
    sa.Column('reference_id', sa.String(length=64), nullable=False),
    sa.Column('status', sa.String(length=12), nullable=False),
    sa.Column('amount', sa.Float(), nullable=False),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('transaction_id', sa.String(length=64), nullable=True),
    sa.Column('reason', sa.String(length=120), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('reviewed_by', sa.String(length=64), nullable=True),
    sa.Column('reviewed_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['bill_id'], ['bills.bill_id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('reference_id')
    )
    _create_index(op.f('ix_payments_bill_id'), 'payments', ['bill_id'], unique=False)
    _create_index('uq_payments_momo_pay_txn', 'payments', ['transaction_id'], unique=True, sqlite_where=sa.text("provider = 'momo_pay' AND status <> 'failed'"), postgresql_where=sa.text("provider = 'momo_pay' AND status <> 'failed'"))
    _create_index('uq_payments_one_pending', 'payments', ['bill_id'], unique=True, sqlite_where=sa.text("status = 'pending'"), postgresql_where=sa.text("status = 'pending'"))


    # PostgreSQL cannot create a foreign key to a table that does not exist yet.
    if op.get_bind().dialect.name == "postgresql":
        keys = sa.inspect(op.get_bind()).get_foreign_keys("customers")
        if not any(k["constrained_columns"] == ["meter_id"] for k in keys):
            op.create_foreign_key("fk_customers_meter_id", "customers", "meters", ["meter_id"], ["meter_id"])


def downgrade():
    raise RuntimeError("The baseline contains financial records. Restore a verified backup instead of dropping it.")
