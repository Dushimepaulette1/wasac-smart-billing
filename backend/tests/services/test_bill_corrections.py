"""Correcting a billed reading: originals stay, adjustments and credits record the change
(app/services/bill_corrections.py, app/services/balance.py)."""
from datetime import datetime, timedelta

import pytest

from app.anomaly.service import submit_reading
from app.models import (
    AccountCredit, Bill, BillAdjustment, BillCorrection, Customer, Meter, Payment, Reading, StaffAction,
)
from app.services import billing
from app.services.balance import available_credit, balances, bill_balance, settle
from support.factories import add_household, add_officer, household_token, make_history, staff_token

METER = "MTR-BC"
CUSTOMER = "CUST-BC"


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def staff(db):
    return {
        "sup1": bearer(staff_token(add_officer(db, "sup1", role="supervisor"))),
        "sup2": bearer(staff_token(add_officer(db, "sup2", role="supervisor"))),
        "officer": bearer(staff_token(add_officer(db, "off1"))),
    }


def billed(db, value, consumption, days_ago, paid=False):
    """A confirmed reading and its bill, as they are in the database."""
    r = Reading(meter_id=METER, submitted_value=value, implied_consumption=consumption, validation_status="valid",
                submission_time=datetime.utcnow() - timedelta(days=days_ago))
    db.add(r)
    db.flush()
    bill = billing.build_bill(CUSTOMER, r.reading_id, consumption)
    bill.created_at = r.submission_time
    db.add(bill)
    db.flush()
    if paid:
        pay(db, bill)
    db.get(Meter, METER).last_reading = value
    db.commit()
    return r, bill


def pay(db, bill, amount=None):
    db.add(Payment(bill_id=bill.bill_id, provider="simulated", reference_id=f"r{bill.bill_id}-{amount}",
                   status="successful", amount=amount or bill.amount_due, currency="RWF"))
    bill.payment_status = "paid"
    db.commit()


@pytest.fixture
def account(db):
    """The worked example: R0 400.000, R1 431.460 (31.46 m³, RWF 21,375), R2 445.000 (13.54 m³, RWF 7,276.20)."""
    add_household(db, METER, [make_history([0.4], start=datetime.utcnow() - timedelta(days=200), start_m3=400.0)[0]])
    r1, b1 = billed(db, 431.46, 31.46, 60)
    r2, b2 = billed(db, 445.0, 13.54, 30)
    assert b1.amount_due == pytest.approx(21375) and b2.amount_due == pytest.approx(7276.2)
    return r1, b1, r2, b2


def correct(c, headers, reading, value="421.460", reason="Meter read again on site", key=None, apply=True):
    return c.post(f"/customers/{CUSTOMER}/readings/{reading.reading_id}/correction", headers=headers,
                  json={"corrected_reading": value, "reason": reason, "request_key": key, "apply": apply})


def snapshot(db):
    bills = [(b.bill_id, b.amount_due, b.consumption_m3, b.payment_status, b.tier1_amount) for b in db.query(Bill).order_by(Bill.bill_id)]
    payments = [(p.id, p.amount, p.status) for p in db.query(Payment).order_by(Payment.id)]
    readings = [(r.reading_id, r.submitted_value, r.implied_consumption) for r in db.query(Reading).order_by(Reading.reading_id)]
    return bills, payments, readings


def test_when_a_later_bill_exists_should_evaluate_both_bills_with_the_exact_amounts(db, anon_client, staff, account):
    r1, b1, r2, b2 = account
    body = correct(anon_client, staff["sup1"], r1, apply=False).json()
    assert body["status"] == "preview" and body["needs_approval"] is True
    first, second = body["adjustments"]
    assert first["bill_id"] == b1.bill_id and first["consumption_after"] == pytest.approx(21.46)
    assert first["amount_after"] == pytest.approx(13159.86) and first["amount_delta"] == pytest.approx(-8215.14)
    assert second["bill_id"] == b2.bill_id and second["consumption_after"] == pytest.approx(23.54)
    assert second["amount_after"] == pytest.approx(14805.14) and second["amount_delta"] == pytest.approx(7528.94)
    assert body["net_delta"] == pytest.approx(-686.20)  # evening out the tiers costs less
    assert db.query(BillCorrection).count() == 0  # a preview stores nothing


def test_when_a_correction_charges_more_should_wait_for_a_different_supervisor(db, anon_client, staff, account):
    r1, b1, r2, b2 = account
    before = snapshot(db)
    body = correct(anon_client, staff["sup1"], r1).json()
    assert body["status"] == "awaiting_approval"
    assert bill_balance(db, b1).charges == pytest.approx(21375)  # nothing applied yet
    assert db.get(Reading, r1.reading_id).corrected_value_m3 is None

    assert anon_client.post(f"/bill-corrections/{body['id']}/approve", headers=staff["sup1"]).status_code == 403
    assert anon_client.post(f"/bill-corrections/{body['id']}/approve", headers=staff["officer"]).status_code == 403
    done = anon_client.post(f"/bill-corrections/{body['id']}/approve", headers=staff["sup2"]).json()
    assert done["status"] == "applied" and done["decided_by"] == "sup2"

    assert bill_balance(db, b1).charges == pytest.approx(13159.86)
    assert bill_balance(db, b2).charges == pytest.approx(14805.14)
    assert snapshot(db) == before  # originals untouched
    assert db.get(Reading, r1.reading_id).corrected_value_m3 == pytest.approx(421.46)
    assert db.get(Meter, METER).last_reading == 445.0  # a later reading exists: the baseline stays


def test_when_the_latest_reading_is_corrected_down_should_apply_at_once_and_move_the_baseline(db, anon_client, staff, account):
    _, _, r2, b2 = account
    body = correct(anon_client, staff["sup1"], r2, "440.000").json()
    assert body["status"] == "applied" and not body["needs_approval"]
    assert bill_balance(db, b2).charges == pytest.approx(billing.calculate_bill(8.54)["total"])
    assert db.get(Meter, METER).last_reading == 440.0
    # The next reading is measured from the corrected value, and history uses it.
    sub = submit_reading(db, db.get(Meter, METER), CUSTOMER, 452.0, method="camera")
    assert sub.consumption_m3 == pytest.approx(12.0)


def test_when_a_paid_bill_is_corrected_down_should_become_credit_used_on_the_next_bill(db, anon_client, staff):
    add_household(db, METER, [make_history([0.4], start=datetime.utcnow() - timedelta(days=200), start_m3=400.0)[0]])
    _, bill = billed(db, 431.46, 31.46, 40, paid=True)
    payments = snapshot(db)[1]
    body = correct(anon_client, staff["sup1"], db.get(Reading, bill.reading_id), "421.460").json()
    assert body["status"] == "applied"
    credit = bill_balance(db, bill).amount_due - billing.calculate_bill(21.46)["total"]
    assert available_credit(db, CUSTOMER) == pytest.approx(credit)
    assert bill_balance(db, bill).outstanding == 0 and snapshot(db)[1] == payments

    sub = submit_reading(db, db.get(Meter, METER), CUSTOMER, 431.46, method="camera")  # 10 m3: RWF 5,400 + ...
    money = bill_balance(db, sub.bill)
    assert money.credit_used == pytest.approx(min(credit, sub.bill.amount_due))
    assert money.outstanding == pytest.approx(max(0, sub.bill.amount_due - credit))
    assert sub.bill.amount_due == billing.calculate_bill(10.0)["total"]  # the bill itself is as issued


def test_when_a_paid_bill_is_corrected_up_should_owe_only_the_difference_after_approval(db, anon_client, staff):
    add_household(db, METER, [make_history([0.4], start=datetime.utcnow() - timedelta(days=200), start_m3=400.0)[0]])
    _, bill = billed(db, 412.0, 12.0, 40, paid=True)
    body = correct(anon_client, staff["sup1"], db.get(Reading, bill.reading_id), "420.000").json()
    assert body["status"] == "awaiting_approval" and bill_balance(db, bill).settled
    anon_client.post(f"/bill-corrections/{body['id']}/approve", headers=staff["sup2"])
    extra = billing.calculate_bill(20.0)["total"] - billing.calculate_bill(12.0)["total"]
    assert bill_balance(db, bill).outstanding == pytest.approx(extra)
    assert db.get(Bill, bill.bill_id).payment_status == "paid"  # the payment record stands


def test_when_an_unpaid_bill_is_corrected_should_change_the_balance_not_the_bill(db, anon_client, staff, account, client):
    _, _, r2, b2 = account
    correct(anon_client, staff["sup1"], r2, "440.000")
    assert db.get(Bill, b2.bill_id).amount_due == pytest.approx(7276.2)
    info = client.get(f"/customers/{CUSTOMER}").json()
    want = billing.calculate_bill(8.54)["total"] + 21375
    assert info["unpaid_amount"] == pytest.approx(want) and info["unpaid_count"] == 2


def test_when_paying_after_a_correction_should_ask_for_the_balance(db, anon_client, staff, account, monkeypatch):
    _, _, r2, b2 = account
    correct(anon_client, staff["sup1"], r2, "440.000")
    monkeypatch.setenv("PAYMENTS_SIMULATE", "1")
    body = anon_client.post(f"/bills/{b2.bill_id}/pay", headers=bearer(household_token())).json()
    assert body["amount"] == billing.whole_francs(billing.calculate_bill(8.54)["total"])
    assert bill_balance(db, b2).settled


def test_when_the_same_request_is_sent_twice_should_correct_once(db, anon_client, staff, account):
    _, _, r2, _ = account
    first = correct(anon_client, staff["sup1"], r2, "440.000", key="k1").json()
    second = correct(anon_client, staff["sup1"], r2, "440.000", key="k1").json()
    assert first["id"] == second["id"]
    assert db.query(BillCorrection).count() == 1 and db.query(BillAdjustment).count() == 1


def test_when_the_value_is_already_recorded_should_refuse(db, anon_client, staff, account):
    _, _, r2, _ = account
    correct(anon_client, staff["sup1"], r2, "440.000")
    assert correct(anon_client, staff["sup1"], r2, "440.000").status_code == 409


@pytest.mark.parametrize("value", ["399.000", "446.000"])
def test_when_the_value_is_outside_the_neighbouring_readings_should_refuse(db, anon_client, staff, account, value):
    r1, *_ = account
    r = correct(anon_client, staff["sup1"], r1, value)
    assert r.status_code == 409 and "negative" in r.json()["detail"]


def test_when_a_reading_is_waiting_for_review_should_refuse(db, anon_client, staff, account):
    _, _, r2, _ = account
    db.add(Reading(meter_id=METER, submitted_value=1.0, submission_time=datetime.utcnow(), validation_status="pending_review"))
    db.commit()
    assert correct(anon_client, staff["sup1"], r2, "440.000").status_code == 409


def test_when_a_payment_is_open_on_the_bill_should_refuse(db, anon_client, staff, account):
    _, _, r2, b2 = account
    db.add(Payment(bill_id=b2.bill_id, provider="momo_pay", reference_id="open", status="pending", amount=1.0, currency="RWF"))
    db.commit()
    r = correct(anon_client, staff["sup1"], r2, "440.000")
    assert r.status_code == 409 and "payment" in r.json()["detail"]


def test_when_the_bills_change_before_approval_should_go_stale(db, anon_client, staff, account):
    r1, b1, *_ = account
    body = correct(anon_client, staff["sup1"], r1).json()
    pay(db, b1)  # the amounts are unchanged, so this alone is fine
    other = correct(anon_client, staff["sup1"], db.query(Reading).order_by(Reading.reading_id.desc()).first(), "440.000")
    assert other.status_code == 200  # the later reading moves the figures underneath the waiting correction
    r = anon_client.post(f"/bill-corrections/{body['id']}/approve", headers=staff["sup2"])
    assert r.status_code == 409 and "changed" in r.json()["detail"]
    assert db.get(BillCorrection, body["id"]).status == "stale"


def test_when_a_correction_is_declined_should_change_nothing(db, anon_client, staff, account):
    r1, b1, *_ = account
    body = correct(anon_client, staff["sup1"], r1).json()
    assert anon_client.post(f"/bill-corrections/{body['id']}/decline", headers=staff["sup1"], json={"reason": "own"}).status_code == 403
    out = anon_client.post(f"/bill-corrections/{body['id']}/decline", headers=staff["sup2"], json={"reason": "Reading was right"}).json()
    assert out["status"] == "declined" and bill_balance(db, b1).charges == pytest.approx(21375)
    assert db.get(Reading, r1.reading_id).corrected_value_m3 is None


def test_when_corrected_should_keep_a_full_audit_trail(db, anon_client, staff, account):
    r1, *_ = account
    body = correct(anon_client, staff["sup1"], r1).json()
    anon_client.post(f"/bill-corrections/{body['id']}/approve", headers=staff["sup2"])
    actions = {(a.username, a.action) for a in db.query(StaffAction).all()}
    assert {("sup1", "bill_correction_requested"), ("sup2", "correction_approved")} <= actions
    row = db.query(StaffAction).filter(StaffAction.action == "bill_correction_requested").one()
    assert "431.460 -> 421.460" in row.detail and "Meter read again on site" in row.detail


def test_when_credit_is_created_or_used_should_be_audited(db, anon_client, staff):
    add_household(db, METER, [make_history([0.4], start=datetime.utcnow() - timedelta(days=200), start_m3=400.0)[0]])
    _, paid_bill = billed(db, 431.46, 31.46, 40, paid=True)
    r3, unpaid = billed(db, 445.0, 13.54, 10)
    correct(anon_client, staff["sup1"], db.get(Reading, r3.reading_id), "440.000")  # lowers the unpaid bill
    correct(anon_client, staff["sup1"], db.get(Reading, paid_bill.reading_id), "429.000")  # credit + charge: approval
    waiting = db.query(BillCorrection).filter(BillCorrection.status == "awaiting_approval").one()
    anon_client.post(f"/bill-corrections/{waiting.id}/approve", headers=staff["sup2"])
    actions = [a.action for a in db.query(StaffAction).all()]
    assert "credit_added" in actions and "credit_applied" in actions
    assert sum(c.amount for c in db.query(AccountCredit).all()) == pytest.approx(available_credit(db, CUSTOMER))


def test_when_a_household_looks_should_see_original_adjustment_and_balance_but_only_its_own(db, anon_client, staff, account):
    _, _, r2, b2 = account
    correct(anon_client, staff["sup1"], r2, "440.000")
    mine = anon_client.get(f"/customers/{CUSTOMER}/bills", headers=bearer(household_token())).json()
    row = next(b for b in mine if b["bill_id"] == b2.bill_id)
    assert row["amount_due"] == pytest.approx(7276.2)
    assert row["adjustments"][0]["reason"] == "Meter read again on site"
    assert row["charges"] == row["outstanding"] == pytest.approx(billing.calculate_bill(8.54)["total"])
    other = bearer(household_token("+250788222333"))
    add_household(db, "MTR-OT", make_history([0.4] * 2), phone="+250788222333")
    assert anon_client.get(f"/customers/{CUSTOMER}/bills", headers=other).status_code == 404


def test_when_an_officer_tries_should_refuse(db, anon_client, staff, account):
    r1, *_ = account
    assert correct(anon_client, staff["officer"], r1).status_code == 403
    assert anon_client.get("/bill-corrections", headers=staff["officer"]).status_code == 403


def test_a_correction_should_use_the_bills_own_tariff(db, anon_client, staff, account, monkeypatch):
    _, _, r2, _ = account
    new = {"version": "v2", "effective_from": "2026-01-01", "tiers": [[5, 900], [10, 900], [15, 900], [None, 900]],
           "service_charge": 5000}
    monkeypatch.setattr(billing, "TARIFFS", billing.TARIFFS + [new])
    body = correct(anon_client, staff["sup1"], r2, "440.000", apply=False).json()
    assert body["adjustments"][0]["tariff_version"] == "v1-provisional"
    assert body["adjustments"][0]["amount_after"] == pytest.approx(round(billing.calculate_bill(8.54, "v1-provisional")["total"], 2))


def test_when_a_bill_is_paid_twice_should_keep_the_extra_as_credit(db, account):
    from app.services.payments import _mark_paid

    _, _, _, b2 = account
    pay(db, b2)
    late = Payment(bill_id=b2.bill_id, provider="momo_sandbox", reference_id="late", status="pending",
                   amount=b2.amount_due, currency="EUR")
    db.add(late)
    db.flush()
    _mark_paid(db, late, b2, "T1")
    db.commit()
    # The credit goes straight to the older unpaid bill, oldest first.
    assert bill_balance(db, db.query(Bill).order_by(Bill.bill_id).first()).credit_used == pytest.approx(b2.amount_due)


def test_settling_twice_should_not_create_credit_twice(db, anon_client, staff):
    add_household(db, METER, [make_history([0.4], start=datetime.utcnow() - timedelta(days=200), start_m3=400.0)[0]])
    _, bill = billed(db, 431.46, 31.46, 40, paid=True)
    correct(anon_client, staff["sup1"], db.get(Reading, bill.reading_id), "421.460")
    credit = available_credit(db, CUSTOMER)
    settle(db, CUSTOMER)
    settle(db, CUSTOMER)
    assert available_credit(db, CUSTOMER) == credit and len(balances(db, CUSTOMER)) == 1


def test_when_a_customer_row_has_old_paid_bills_without_payments_should_treat_them_as_paid(db):
    add_household(db, METER, [make_history([0.4])[0]])
    bill = Bill(customer_id=CUSTOMER, consumption_m3=5, amount_due=2750.0, payment_status="paid")
    db.add(bill)
    db.commit()
    assert bill_balance(db, bill).settled and db.get(Customer, CUSTOMER)


def test_when_credit_waited_for_an_open_attempt_should_use_it_on_the_next_try(db, anon_client, staff, account, monkeypatch):
    _, b1, _, _ = account
    db.add(AccountCredit(customer_id=CUSTOMER, amount=1000.0, kind="overpayment"))
    db.commit()
    monkeypatch.setenv("PAYMENTS_SIMULATE", "1")
    body = anon_client.post(f"/bills/{b1.bill_id}/pay", headers=bearer(household_token())).json()
    assert body["amount"] == pytest.approx(b1.amount_due - 1000)
