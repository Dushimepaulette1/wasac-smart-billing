"""Requests that arrive at the same moment, on a real PostgreSQL database (row locks and partial
unique indexes behave as in production; SQLite runs one writer at a time and cannot show this).

    TEST_POSTGRES_URL=postgresql://postgres:test@localhost:5433/mubazi_test pytest -m postgres

Skipped without TEST_POSTGRES_URL. The URL must point at a local database whose name contains
"test": every test drops and recreates all tables in it.
"""
import os
import threading
import time
from datetime import datetime, timedelta
from urllib.parse import urlparse

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.anomaly.review import ReviewError, resolve_flag
from app.anomaly.service import ReadingRefused, submit_reading
from app.db.init_db import add_late_indexes
from app.db.session import Base
from app.models import AnomalyFlag, Bill, Meter, Payment, Reading
from app.services import momo, payments
from support.factories import add_household, make_history

pytestmark = pytest.mark.postgres
URL = os.getenv("TEST_POSTGRES_URL", "")


def _safe(url: str) -> bool:
    parts = urlparse(url)
    return (parts.scheme.startswith("postgresql") and parts.hostname in ("localhost", "127.0.0.1")
            and "test" in parts.path and url != os.getenv("DATABASE_URL"))


if not URL:
    pytest.skip("TEST_POSTGRES_URL not set: PostgreSQL concurrency tests skipped", allow_module_level=True)
if not _safe(URL):
    pytest.fail("TEST_POSTGRES_URL must be a local database with 'test' in its name", pytrace=False)


@pytest.fixture
def pg():
    engine = create_engine(URL, pool_size=20, max_overflow=10)
    with engine.begin() as conn:  # customers and meters reference each other: drop_all cannot order them
        conn.exec_driver_sql("DROP SCHEMA public CASCADE")
        conn.exec_driver_sql("CREATE SCHEMA public")
    Base.metadata.create_all(engine)
    make = sessionmaker(bind=engine, autoflush=False)
    yield make
    engine.dispose()


def race(n, work):
    """Run work(i) in n threads that start together; returns [(result or exception)] by thread."""
    barrier = threading.Barrier(n)
    out = [None] * n

    def run(i):
        barrier.wait()
        try:
            out[i] = work(i)
        except Exception as e:  # noqa: BLE001  the outcome under test
            out[i] = e

    threads = [threading.Thread(target=run, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(60)
    return out


class SlowMtn:
    """MTN's API, answering slowly so that racing requests overlap."""

    def __init__(self, status="PENDING"):
        self.posts, self.status, self.lock = 0, status, threading.Lock()

    def post(self, url, json=None, headers=None, auth=None, timeout=None):
        if url.endswith("/collection/token/"):
            return Resp(200, {"access_token": "tok", "expires_in": 3600})
        with self.lock:
            self.posts += 1
        time.sleep(0.2)
        return Resp(202, None)

    def get(self, url, headers=None, timeout=None):
        time.sleep(0.05)
        return Resp(200, {"status": self.status,
                          "financialTransactionId": "987" if self.status == "SUCCESSFUL" else None})


class Resp:
    def __init__(self, code, body):
        self.status_code, self._body = code, body

    def json(self):
        return self._body


@pytest.fixture
def mtn(monkeypatch):
    fake = SlowMtn()
    for k, v in {"MOMO_SUBSCRIPTION_KEY": "sub", "MOMO_API_USER": "user", "MOMO_API_KEY": "key"}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(momo.httpx, "post", fake.post)
    monkeypatch.setattr(momo.httpx, "get", fake.get)
    momo.reset_token()
    yield fake
    momo.reset_token()


@pytest.fixture
def receipts(monkeypatch):
    sent = []
    monkeypatch.setattr(payments, "send_sms", lambda phone, text, **kw: sent.append(text) or True)
    return sent


def make_bill(make, meter="MTR-PG", amount=6460.0):
    with make() as db:
        customer_id = add_household(db, meter, make_history([0.4] * 3))
        bill = Bill(customer_id=customer_id, consumption_m3=12, amount_due=amount, payment_status="unpaid")
        db.add(bill)
        db.commit()
        return bill.bill_id


@pytest.fixture
def slow_lookup(monkeypatch):
    """Widen the gap between "no open attempt" and the insert, so racing requests overlap."""
    real = payments._open_attempt

    def slow(db, bill_id):
        found = real(db, bill_id)
        time.sleep(0.2)
        return found

    monkeypatch.setattr(payments, "_open_attempt", slow)


def no_bill_lock(monkeypatch):
    monkeypatch.setattr(payments, "_lock_bill", lambda db, bill_id: db.get(Bill, bill_id))


@pytest.mark.parametrize("guard", ["bill lock and index", "index alone"])
def test_when_ten_pay_requests_arrive_at_once_should_open_one_attempt_and_prompt_once(
        pg, mtn, slow_lookup, monkeypatch, guard):
    if guard == "index alone":
        no_bill_lock(monkeypatch)
    bill_id = make_bill(pg)

    def pay(_):
        with pg() as db:
            return payments.start_payment(db, db.get(Bill, bill_id), "+250788000111").id

    ids = race(10, pay)
    assert all(isinstance(i, int) for i in ids), ids
    assert len(set(ids)) == 1 and mtn.posts == 1
    with pg() as db:
        assert db.query(Payment).filter(Payment.bill_id == bill_id).count() == 1


def test_without_the_lock_and_the_index_ten_pay_requests_would_prompt_more_than_once(pg, mtn, slow_lookup, monkeypatch):
    """Shows the race test above can fail: with every guard removed, requests open several attempts.
    (settle's lock on the customer row also serialises them, so it is removed too.)"""
    no_bill_lock(monkeypatch)
    monkeypatch.setattr(payments, "settle", lambda *a, **k: None)
    with pg.kw["bind"].begin() as conn:
        conn.exec_driver_sql("DROP INDEX uq_payments_one_pending")
    bill_id = make_bill(pg)

    def pay(_):
        with pg() as db:
            return payments.start_payment(db, db.get(Bill, bill_id), "+250788000111").id

    race(10, pay)
    assert mtn.posts > 1


def test_when_many_status_checks_see_success_at_once_should_mark_paid_once_with_one_receipt(pg, mtn, receipts):
    bill_id = make_bill(pg)
    with pg() as db:
        payment_id = payments.start_payment(db, db.get(Bill, bill_id), "+250788000111").id
    mtn.status = "SUCCESSFUL"

    def check(_):
        with pg() as db:
            return payments.refresh(db, db.get(Payment, payment_id)).status

    assert race(6, check) == ["successful"] * 6
    assert len(receipts) == 1
    with pg() as db:
        assert db.get(Bill, bill_id).payment_status == "paid"


def test_when_two_pending_attempts_are_inserted_for_one_bill_should_be_refused_by_the_database(pg):
    bill_id = make_bill(pg)
    with pg() as db:
        for ref in ("a", "b"):
            db.add(Payment(bill_id=bill_id, provider="momo_sandbox", reference_id=ref, status="pending",
                           amount=1.0, currency="EUR"))
        with pytest.raises(IntegrityError):
            db.commit()


def test_when_two_officers_confirm_one_momo_pay_payment_at_once_should_mark_it_paid_once(pg, receipts):
    bill_id = make_bill(pg)
    with pg() as db:
        p = payments.start_payment(db, db.get(Bill, bill_id), "+250788000111")
        payments.submit_reference(db, p, "MP2610291234")
        payment_id = p.id

    def confirm(_):
        with pg() as db:
            return payments.confirm(db, db.get(Payment, payment_id)).status

    out = race(4, confirm)
    assert out.count("successful") == 1
    assert all(isinstance(o, payments.PaymentError) and o.status_code == 409 for o in out if o != "successful")
    assert len(receipts) == 1


def test_when_one_momo_pay_transaction_id_is_given_for_two_bills_at_once_should_accept_it_once(pg):
    first, second = make_bill(pg, "MTR-PG1"), make_bill(pg, "MTR-PG2")
    with pg() as db:
        ids = [payments.start_payment(db, db.get(Bill, b), "+250788000111").id for b in (first, second)]

    def give(i):
        with pg() as db:
            return payments.submit_reference(db, db.get(Payment, ids[i]), "MP2610291234").id

    out = race(2, give)
    assert sum(isinstance(o, int) for o in out) == 1
    assert sum(isinstance(o, payments.PaymentError) and o.status_code == 409 for o in out) == 1


def test_when_two_officers_accept_one_held_reading_at_once_should_bill_it_once(pg):
    with pg() as db:
        points = make_history([0.4] * 6, start=datetime.utcnow() - timedelta(days=210))
        customer_id = add_household(db, "MTR-PGR", points)
        meter = db.get(Meter, "MTR-PGR")
        sub = submit_reading(db, meter, customer_id, points[-1].reading_m3 + 200, method="camera")  # SPIKE: held
        assert sub.reading.validation_status == "pending_review"
        flag_id = sub.anomaly.flag_id

    def accept(_):
        with pg() as db:
            return resolve_flag(db, db.get(AnomalyFlag, flag_id), "accept").outcome

    out = race(3, accept)
    assert out.count("accept") == 1
    assert all(isinstance(o, ReviewError) and o.status_code == 409 for o in out if o != "accept")
    with pg() as db:
        assert db.query(Bill).count() == 1


def test_when_a_household_sends_two_readings_at_once_should_store_and_bill_one(pg):
    with pg() as db:
        points = make_history([0.4] * 6, start=datetime.utcnow() - timedelta(days=210))
        customer_id = add_household(db, "MTR-PGS", points)
        last = points[-1].reading_m3

    def send(i):
        with pg() as db:
            sub = submit_reading(db, db.get(Meter, "MTR-PGS"), customer_id, last + 12 + i * 0.5, method="ussd",
                                 household=True)
            return sub.reading.reading_id

    out = race(2, send)
    assert sum(isinstance(o, int) for o in out) == 1
    assert sum(isinstance(o, ReadingRefused) for o in out) == 1
    with pg() as db:
        assert db.query(Bill).count() == 1
        assert db.query(Reading).filter(Reading.meter_id == "MTR-PGS").count() == len(points) + 1


def test_when_an_older_postgres_database_starts_should_add_the_partial_indexes(pg):
    engine = pg.kw["bind"]
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP INDEX IF EXISTS uq_payments_one_pending")
        conn.exec_driver_sql("DROP INDEX IF EXISTS uq_payments_momo_pay_txn")
    add_late_indexes(engine)
    with engine.connect() as conn:
        names = {r[0] for r in conn.exec_driver_sql("SELECT indexname FROM pg_indexes WHERE tablename = 'payments'")}
    assert {"uq_payments_one_pending", "uq_payments_momo_pay_txn"} <= names


def _billed_account(make):
    from app.services import billing

    with make() as db:
        customer_id = add_household(db, "MTR-PGC", make_history([0.4], start=datetime.utcnow() - timedelta(days=200), start_m3=400.0))
        reading = Reading(meter_id="MTR-PGC", submitted_value=431.46, validation_status="valid",
                          submission_time=datetime.utcnow() - timedelta(days=30))
        db.add(reading)
        db.flush()
        db.add(billing.build_bill(customer_id, reading.reading_id, 31.46))
        db.get(Meter, "MTR-PGC").last_reading = 431.46
        db.commit()
        return reading.reading_id


def test_when_the_same_correction_is_sent_at_once_should_adjust_once(pg):
    from app.models import BillAdjustment, BillCorrection
    from app.services.bill_corrections import request_correction

    reading_id = _billed_account(pg)

    def send(_):
        with pg() as db:
            return request_correction(db, db.get(Reading, reading_id), 421.46, "Meter read on site", "sup1", "same-key").id

    out = race(4, send)
    assert len(set(out)) == 1 and isinstance(out[0], int), out
    with pg() as db:
        assert db.query(BillCorrection).count() == 1 and db.query(BillAdjustment).count() == 1


def test_when_two_supervisors_approve_at_once_should_apply_once(pg):
    from app.models import AccountCredit, BillCorrection
    from app.services.bill_corrections import BillCorrectionError, approve_correction, request_correction

    reading_id = _billed_account(pg)
    with pg() as db:
        correction_id = request_correction(db, db.get(Reading, reading_id), 440.0, "Meter read on site", "sup1", "up").id
        assert db.get(BillCorrection, correction_id).status == "awaiting_approval"

    def approve(i):
        with pg() as db:
            return approve_correction(db, correction_id, f"sup{i + 2}").status

    out = race(3, approve)
    assert out.count("applied") == 1
    assert all(isinstance(o, BillCorrectionError) and o.status_code == 409 for o in out if o != "applied"), out
    with pg() as db:
        assert db.query(AccountCredit).count() == 0


def test_when_an_older_postgres_database_starts_should_add_the_late_columns(pg):
    from sqlalchemy import inspect

    from app.db.init_db import add_late_columns

    engine = pg.kw["bind"]
    with engine.begin() as conn:
        conn.exec_driver_sql("ALTER TABLE bills DROP COLUMN tariff_version")
        conn.exec_driver_sql("ALTER TABLE readings DROP COLUMN corrected_value_m3")
    add_late_columns(engine)
    assert "tariff_version" in {c["name"] for c in inspect(engine).get_columns("bills")}
    assert "corrected_value_m3" in {c["name"] for c in inspect(engine).get_columns("readings")}


def test_when_two_bills_settle_at_once_should_spend_a_credit_once(pg):
    from app.models import AccountCredit
    from app.services.balance import available_credit, settle

    with pg() as db:
        customer_id = add_household(db, "MTR-PGK", make_history([0.4] * 2))
        for _ in range(2):
            db.add(Bill(customer_id=customer_id, consumption_m3=5, amount_due=2750.0, payment_status="unpaid"))
        db.add(AccountCredit(customer_id=customer_id, amount=1000.0, kind="overpayment"))
        db.commit()

    def run(_):
        with pg() as db:
            settle(db, customer_id)
            db.commit()
            return True

    assert race(6, run) == [True] * 6
    with pg() as db:
        assert available_credit(db, customer_id) == 0
        assert db.query(AccountCredit).filter(AccountCredit.kind == "applied").count() == 1
