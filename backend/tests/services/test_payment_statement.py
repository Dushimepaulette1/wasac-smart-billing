"""The list of payments received, which an officer's confirmation is checked against."""
import pytest

from app.models import Bill, PaymentStatementEntry, StaffAction
from app.services import payments
from app.services.billing import build_bill
from app.services.payment_statement import (
    AMOUNT_DIFFERS, MATCHED, NOT_FOUND, StatementError, import_statement, parse_statement, statement_status,
)
from app.models import Reading
from support.clients import signed_in_client
from support.factories import add_household, add_officer, make_history

PHONE = "+250788000111"


@pytest.fixture
def claimed(db, monkeypatch):
    """A MoMo Pay attempt with a transaction ID, waiting for an officer."""
    for name in ("MOMO_SUBSCRIPTION_KEY", "MOMO_API_USER", "MOMO_API_KEY", "PAYMENTS_SIMULATE"):
        monkeypatch.delenv(name, raising=False)
    customer_id = add_household(db, "MTR-S", make_history([0.4] * 3))
    reading = db.query(Reading).filter(Reading.meter_id == "MTR-S").order_by(Reading.reading_id.desc()).first()
    bill = build_bill(customer_id, reading.reading_id, 10.0)
    db.add(bill)
    db.commit()
    return payments.submit_reference(db, payments.start_payment(db, bill, PHONE), "TXN123")


@pytest.fixture
def supervisor(db):
    add_officer(db, username="sup1", role="supervisor")
    fastapi_app, c = signed_in_client(db, "sup1")
    yield c
    fastapi_app.dependency_overrides.clear()


def statement(db, *rows):
    db.add_all(PaymentStatementEntry(transaction_id=t, amount=a, uploaded_by="sup1") for t, a in rows)
    db.commit()


def test_with_no_list_the_officers_check_stands(db, claimed):
    assert statement_status(db, "TXN123", claimed.amount) is None
    assert payments.confirm(db, claimed).status == "successful"


def test_a_matching_payment_can_be_confirmed(db, claimed):
    statement(db, ("TXN123", claimed.amount))
    assert statement_status(db, "txn123 ", claimed.amount) == MATCHED
    assert payments.confirm(db, claimed).status == "successful"


def test_an_id_not_on_the_list_cannot_be_confirmed(db, claimed):
    statement(db, ("OTHER", claimed.amount))
    assert statement_status(db, "TXN123", claimed.amount) == NOT_FOUND
    with pytest.raises(payments.PaymentError) as refused:
        payments.confirm(db, claimed)
    assert refused.value.status_code == 409
    assert db.get(Bill, claimed.bill_id).payment_status != "paid"


def test_a_different_amount_cannot_be_confirmed(db, claimed):
    statement(db, ("TXN123", claimed.amount - 500))
    assert statement_status(db, "TXN123", claimed.amount) == AMOUNT_DIFFERS
    with pytest.raises(payments.PaymentError):
        payments.confirm(db, claimed)


def test_parsing_lists_each_mistake_by_line():
    rows, errors = parse_statement("transaction_id,amount,reference\nA1,5000,KGL-1\n,100,\nA2,abc,\nA1,10,\nA3,-5,\n")
    assert rows == [("A1", 5000.0, "KGL-1")]
    assert errors == ["3:transaction_id", "4:amount", "5:duplicate", "6:amount"]


def test_a_file_without_the_columns_is_refused():
    with pytest.raises(StatementError):
        parse_statement("name,phone\nA,B\n")


def test_a_file_with_a_mistake_saves_nothing(db):
    result = import_statement(db, "transaction_id,amount\nA1,5000\nA2,abc\n", "sup1")
    assert result.errors == ["3:amount"] and result.added == 0
    db.commit()
    assert db.query(PaymentStatementEntry).count() == 0


def test_uploading_again_updates_a_row(db):
    import_statement(db, "transaction_id,amount\nA1,5000\n", "sup1")
    db.commit()
    result = import_statement(db, "transaction_id,amount\nA1,6000\nA2,100\n", "sup1")
    db.commit()
    assert (result.added, result.updated) == (1, 1)
    assert db.get(PaymentStatementEntry, "A1").amount == 6000


def test_a_supervisor_uploads_and_it_is_logged(db, supervisor, claimed):
    r = supervisor.post("/api/payments/statement", json={"csv": f"transaction_id,amount\nTXN123,{claimed.amount}\n"})
    assert r.status_code == 200 and r.json()["added"] == 1
    assert db.query(StaffAction).filter(StaffAction.action == "payment_statement_uploaded").count() == 1
    row = next(x for x in supervisor.get("/api/payments/to-check").json() if x["id"] == claimed.id)
    assert row["statement"] == MATCHED


def test_an_officer_cannot_upload(client):
    assert client.post("/api/payments/statement", json={"csv": "transaction_id,amount\nA,1\n"}).status_code == 403


def test_a_bad_file_is_refused_with_a_reason(supervisor):
    assert supervisor.post("/api/payments/statement", json={"csv": "name\nA\n"}).status_code == 422
