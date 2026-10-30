"""Historical first bills that charged a whole meter register: a supervisor gives the true start.
Original bills and payments stay; adjustments and credits record the change."""
from datetime import datetime, timedelta

import pytest

from app.models import AccountCredit, Bill, BillCorrection, Customer, Meter, Payment, Reading, StaffAction
from app.services import billing
from app.services.balance import available_credit, bill_balance
from scripts.find_first_reading_bills import find
from support.factories import add_officer, household_token, staff_token

METER = "MTR-BL"
CUSTOMER = "CUST-BL"
TOTAL = billing.calculate_bill


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def staff(db):
    return {name: bearer(staff_token(add_officer(db, name, role=role)))
            for name, role in (("sup1", "supervisor"), ("sup2", "supervisor"), ("off1", "officer"))}


def billed(db, value, consumption, days_ago, version=None):
    r = Reading(meter_id=METER, submitted_value=value, implied_consumption=consumption, validation_status="valid",
                submission_time=datetime.utcnow() - timedelta(days=days_ago))
    db.add(r)
    db.flush()
    bill = billing.build_bill(CUSTOMER, r.reading_id, consumption)
    bill.created_at, bill.tariff_version = r.submission_time, version
    db.add(bill)
    db.get(Meter, METER).last_reading = value
    db.commit()
    return r, bill


def pay(db, bill, amount):
    db.add(Payment(bill_id=bill.bill_id, provider="simulated", reference_id=f"p{bill.bill_id}-{amount}",
                   status="successful", amount=amount, currency="RWF"))
    if amount >= bill.amount_due:
        bill.payment_status = "paid"
    db.commit()


@pytest.fixture
def first(db):
    """The bug: added with last_reading 0, and the first reading of 431.460 billed in full."""
    db.add(Meter(meter_id=METER, last_reading=0.0))
    db.flush()
    db.add(Customer(customer_id=CUSTOMER, name="Old", phone="+250788000111", meter_id=METER))
    db.flush()
    db.get(Meter, METER).customer_id = CUSTOMER
    db.commit()
    return billed(db, 431.46, 431.46, 90)


def baseline(c, headers, reading, start="420.000", corrected="431.460", apply=True, key=None):
    return c.post(f"/customers/{CUSTOMER}/readings/{reading.reading_id}/correction", headers=headers, json={
        "corrected_reading": corrected, "start_reading": start, "reason": "Old meter card shows the start",
        "request_key": key, "apply": apply,
    })


def records(db):
    return ([(b.bill_id, b.amount_due, b.consumption_m3, b.payment_status) for b in db.query(Bill).order_by(Bill.bill_id)],
            [(p.id, p.amount, p.status) for p in db.query(Payment).order_by(Payment.id)],
            [(r.reading_id, r.submitted_value) for r in db.query(Reading).order_by(Reading.reading_id)])


def test_the_finder_should_list_it_until_the_baseline_is_set(db, anon_client, staff, first):
    r, bill = first
    assert [b.bill_id for b, _, _ in find(db)] == [bill.bill_id]
    baseline(anon_client, staff["sup1"], r)
    assert find(db) == []


def test_when_unpaid_should_lower_the_balance_and_keep_the_bill(db, anon_client, staff, first):
    r, bill = first
    before = records(db)
    body = baseline(anon_client, staff["sup1"], r).json()
    assert body["status"] == "applied" and body["kind"] == "baseline" and body["start_m3"] == 420.0
    assert bill_balance(db, bill).outstanding == pytest.approx(TOTAL(11.46)["total"])
    assert records(db) == before
    assert db.get(Reading, r.reading_id).corrected_value_m3 is None  # the reading itself was right


def test_when_fully_paid_should_become_credit_with_the_payment_kept(db, anon_client, staff, first):
    r, bill = first
    pay(db, bill, bill.amount_due)
    payments = records(db)[1]
    baseline(anon_client, staff["sup1"], r)
    assert available_credit(db, CUSTOMER) == pytest.approx(bill.amount_due - TOTAL(11.46)["total"], abs=0.01)
    assert bill_balance(db, bill).settled and records(db)[1] == payments


def test_when_partly_paid_with_less_than_the_right_amount_should_leave_the_rest_owing(db, anon_client, staff, first):
    r, bill = first
    pay(db, bill, 5000)
    baseline(anon_client, staff["sup1"], r)
    assert bill_balance(db, bill).outstanding == pytest.approx(TOTAL(11.46)["total"] - 5000)
    assert available_credit(db, CUSTOMER) == 0


def test_when_partly_paid_with_more_than_the_right_amount_should_credit_the_difference(db, anon_client, staff, first):
    r, bill = first
    pay(db, bill, 50000)
    baseline(anon_client, staff["sup1"], r)
    assert bill_balance(db, bill).outstanding == 0
    assert available_credit(db, CUSTOMER) == pytest.approx(50000 - TOTAL(11.46)["total"])


def test_when_the_first_reading_was_only_ever_a_starting_point_should_owe_nothing(db, anon_client, staff, first):
    r, bill = first
    body = baseline(anon_client, staff["sup1"], r, start="431.460").json()
    assert body["adjustments"][0]["amount_after"] == 0 and body["adjustments"][0]["consumption_after"] == 0
    assert bill_balance(db, bill).charges == 0 and bill_balance(db, bill).settled


def test_when_later_bills_exist_and_the_reading_is_right_should_leave_them_alone(db, anon_client, staff, first):
    r, bill = first
    _, second = billed(db, 443.46, 12.0, 60)
    _, third = billed(db, 455.46, 12.0, 30)
    body = baseline(anon_client, staff["sup1"], r).json()
    assert [a["bill_id"] for a in body["adjustments"]] == [bill.bill_id]
    assert bill_balance(db, second).charges == second.amount_due and bill_balance(db, third).charges == third.amount_due


def test_when_the_first_reading_was_also_wrong_should_recalculate_the_next_bill_only(db, anon_client, staff, first):
    r, bill = first
    _, second = billed(db, 443.46, 12.0, 60)
    _, third = billed(db, 455.46, 12.0, 30)
    body = baseline(anon_client, staff["sup1"], r, corrected="430.000").json()  # next bill: 13.46 m3, charges more
    assert body["status"] == "awaiting_approval"
    assert [a["bill_id"] for a in body["adjustments"]] == [bill.bill_id, second.bill_id]
    assert body["adjustments"][1]["consumption_after"] == pytest.approx(13.46)
    assert anon_client.post(f"/bill-corrections/{body['id']}/approve", headers=staff["sup2"]).json()["status"] == "applied"
    assert bill_balance(db, second).charges == pytest.approx(TOTAL(13.46)["total"])
    assert bill_balance(db, third).charges == third.amount_due
    assert db.get(Meter, METER).last_reading == 455.46


def test_when_credit_is_created_should_pay_the_later_unpaid_bills_oldest_first(db, anon_client, staff, first):
    r, bill = first
    pay(db, bill, bill.amount_due)
    _, second = billed(db, 443.46, 12.0, 60)
    _, third = billed(db, 455.46, 12.0, 30)
    baseline(anon_client, staff["sup1"], r)
    assert bill_balance(db, second).settled and bill_balance(db, third).settled
    spent = second.amount_due + third.amount_due
    assert available_credit(db, CUSTOMER) == pytest.approx(bill.amount_due - TOTAL(11.46)["total"] - spent, abs=0.01)
    assert db.query(StaffAction).filter(StaffAction.action == "credit_applied").count() == 2


def test_should_use_each_bills_own_tariff_version(db, anon_client, staff, first, monkeypatch):
    r, bill = first
    _, second = billed(db, 443.46, 12.0, 60)
    new = {"version": "v2", "effective_from": "2020-01-01", "tiers": [[5, 900], [10, 900], [15, 900], [None, 900]], "service_charge": 3000}
    monkeypatch.setattr(billing, "TARIFFS", billing.TARIFFS + [new])
    second.tariff_version = "v2"
    db.commit()
    body = baseline(anon_client, staff["sup1"], r, corrected="430.000", apply=False).json()
    assert [a["tariff_version"] for a in body["adjustments"]] == ["v1-provisional", "v2"]
    assert body["adjustments"][1]["amount_after"] == pytest.approx(billing.calculate_bill(13.46, "v2")["total"])


def test_when_a_baseline_change_increases_a_bill_should_need_someone_else(db, anon_client, staff, first):
    r, bill = first
    billed(db, 443.46, 12.0, 60)
    body = baseline(anon_client, staff["sup1"], r, corrected="430.000").json()
    assert anon_client.post(f"/bill-corrections/{body['id']}/approve", headers=staff["sup1"]).status_code == 403
    assert db.query(AccountCredit).count() == 0


def test_a_bill_with_a_real_start_should_not_take_a_baseline(db, anon_client, staff, first):
    r, _ = first
    second, _ = billed(db, 443.46, 12.0, 60)
    assert baseline(anon_client, staff["sup1"], second, start="440.000", corrected="443.460").status_code == 409


def test_when_the_baseline_is_already_set_should_refuse_a_second(db, anon_client, staff, first):
    r, _ = first
    baseline(anon_client, staff["sup1"], r)
    assert baseline(anon_client, staff["sup1"], r, start="425.000").status_code == 409


def test_a_start_above_the_reading_should_be_refused(db, anon_client, staff, first):
    assert baseline(anon_client, staff["sup1"], first[0], start="500.000").status_code == 409


def test_a_preview_should_store_nothing_and_a_repeat_should_correct_once(db, anon_client, staff, first):
    r, _ = first
    assert baseline(anon_client, staff["sup1"], r, apply=False).json()["status"] == "preview"
    assert db.query(BillCorrection).count() == 0
    assert baseline(anon_client, staff["sup1"], r, key="k").json()["id"] == baseline(anon_client, staff["sup1"], r, key="k").json()["id"]


def test_an_officer_should_be_refused(anon_client, staff, first):
    assert baseline(anon_client, staff["off1"], first[0]).status_code == 403


def test_staff_and_household_should_see_it_flagged_and_the_corrected_volume(db, anon_client, staff, first):
    r, bill = first
    row = anon_client.get(f"/customers/{CUSTOMER}/bills", headers=staff["sup1"]).json()[0]
    assert row["unknown_start"] is True
    baseline(anon_client, staff["sup1"], r)
    row = anon_client.get(f"/customers/{CUSTOMER}/bills", headers=bearer(household_token())).json()[0]
    assert row["unknown_start"] is False and row["consumption_m3"] == 431.46
    assert row["consumption_current"] == pytest.approx(11.46)
