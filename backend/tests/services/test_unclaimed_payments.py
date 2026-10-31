"""A MoMo Pay attempt with no transaction ID is not a payment yet: the household tapped Pay and may
never have paid. It must not hold anything up. A top-up after a correction is not a double payment."""
from datetime import datetime

import pytest

from app.models import Meter, Reading
from app.models.bill_correction import OVERPAYMENT, AccountCredit
from app.services import payments
from app.services.balance import available_credit, bill_balance
from app.services.bill_corrections import approve_correction, request_correction
from app.services.billing import build_bill
from support.factories import add_household, make_history

PHONE = "+250788000111"


@pytest.fixture
def billed(db):
    customer_id = add_household(db, "MTR-U", make_history([0.4] * 3))
    meter = db.get(Meter, "MTR-U")
    value = round(meter.last_reading + 12, 3)
    reading = Reading(meter_id="MTR-U", submitted_value=value, implied_consumption=12.0,
                      validation_status="valid", submission_time=datetime.utcnow())
    db.add(reading)
    db.flush()
    bill = build_bill(customer_id, reading.reading_id, 12.0)
    db.add(bill)
    meter.last_reading = value
    db.commit()
    return customer_id, reading, bill


@pytest.fixture
def receipts(monkeypatch):
    sent = []
    monkeypatch.setattr(payments, "send_sms", lambda phone, text, **kw: sent.append(text) or True)
    return sent


def pay_by_momo_pay(db, bill, transaction_id):
    attempt = payments.start_payment(db, bill, PHONE)
    payments.submit_reference(db, attempt, transaction_id)
    return payments.confirm(db, attempt)


def test_when_a_household_tapped_pay_and_left_should_still_allow_a_correction(db, billed):
    _, reading, bill = billed
    payments.start_payment(db, bill, PHONE)
    correction = request_correction(db, reading, reading.submitted_value - 2, "wrong digit", "sup1", "k1")
    assert correction.status == "applied"
    assert bill_balance(db, bill).charges < bill.amount_due


def test_when_a_transaction_id_was_given_should_still_wait_for_the_officer(db, billed):
    from app.services.bill_corrections import BillCorrectionError

    _, reading, bill = billed
    payments.submit_reference(db, payments.start_payment(db, bill, PHONE), "MP1111")
    with pytest.raises(BillCorrectionError, match="still open"):
        request_correction(db, reading, reading.submitted_value - 2, "wrong digit", "sup1", "k1")


def test_when_a_household_has_credit_should_use_it_despite_an_abandoned_attempt(db, billed):
    customer_id, _, bill = billed
    payments.start_payment(db, bill, PHONE)
    db.add(AccountCredit(customer_id=customer_id, amount=2000.0, kind=OVERPAYMENT))
    db.commit()
    again = payments.start_payment(db, bill, PHONE)
    assert again.amount == payments.whole_francs(bill.amount_due - 2000)
    assert available_credit(db, customer_id) == 0


def test_when_a_transaction_id_was_given_should_hold_credit_back_for_that_amount(db, billed):
    customer_id, _, bill = billed
    payments.submit_reference(db, payments.start_payment(db, bill, PHONE), "MP1111")
    db.add(AccountCredit(customer_id=customer_id, amount=2000.0, kind=OVERPAYMENT))
    db.commit()
    payments.start_payment(db, bill, PHONE)
    assert available_credit(db, customer_id) == 2000.0


def test_when_a_bill_goes_up_and_the_difference_is_paid_should_send_a_receipt_and_not_say_paid_twice(
        db, billed, receipts):
    _, reading, bill = billed
    pay_by_momo_pay(db, bill, "MP1111")
    correction = request_correction(db, reading, reading.submitted_value + 5, "digit missed", "sup1", "k2")
    approve_correction(db, correction.id, "sup2")
    assert bill_balance(db, bill).outstanding > 0

    pay_by_momo_pay(db, bill, "MP2222")
    assert len(receipts) == 2
    assert payments.payments_paid_twice(db) == []
    assert bill_balance(db, bill).settled


def test_when_a_settled_bill_is_paid_again_should_say_paid_twice_with_no_second_receipt(db, billed, receipts):
    _, _, bill = billed
    first = pay_by_momo_pay(db, bill, "MP1111")
    second = payments.Payment(bill_id=bill.bill_id, provider="momo_pay", reference_id="r2", status="pending",
                              amount=first.amount, currency="RWF", transaction_id="MP2222")
    db.add(second)
    db.commit()
    payments.confirm(db, second)
    assert [p.id for p, _, _ in payments.payments_paid_twice(db)] == [second.id]
    assert len(receipts) == 1
