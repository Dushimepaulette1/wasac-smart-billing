"""Paying bills: simulated without MoMo keys, MTN Mobile Money "Request to Pay" with them."""
from datetime import datetime, timedelta

import pytest

from app.models import Bill
from app.models.payment import Payment
from app.services import momo
from support.factories import add_household, make_history


class FakeMtn:
    """Stands in for MTN's API: token, request to pay, and a status that can be scripted."""

    def __init__(self):
        self.requests = []
        self.statuses = ["SUCCESSFUL"]
        self.reason = None
        self.refuse_request = False

    def post(self, url, json=None, headers=None, auth=None, timeout=None):
        if url.endswith("/collection/token/"):
            return Response(200, {"access_token": "tok", "expires_in": 3600})
        self.requests.append({"url": url, "json": json, "headers": headers})
        return Response(500 if self.refuse_request else 202, None)

    def get(self, url, headers=None, timeout=None):
        status = self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]
        body = {"status": status, "financialTransactionId": "987654321" if status == "SUCCESSFUL" else None}
        if self.reason:
            body["reason"] = {"code": "PAYER_NOT_FOUND", "message": self.reason}
        return Response(200, body)


class Response:
    def __init__(self, status_code, body):
        self.status_code, self._body = status_code, body

    def json(self):
        return self._body


@pytest.fixture
def bill(db):
    customer_id = add_household(db, "MTR-PAY", make_history([0.4] * 3))
    b = Bill(customer_id=customer_id, consumption_m3=12, amount_due=6460.0, payment_status="unpaid")
    db.add(b)
    db.commit()
    return b


@pytest.fixture
def mtn(monkeypatch):
    fake = FakeMtn()
    for k, v in {"MOMO_SUBSCRIPTION_KEY": "sub", "MOMO_API_USER": "user", "MOMO_API_KEY": "key"}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(momo.httpx, "post", fake.post)
    monkeypatch.setattr(momo.httpx, "get", fake.get)
    momo.reset_token()
    yield fake
    momo.reset_token()


def test_when_payments_are_simulated_should_mark_the_bill_paid_at_once(db, household_client, bill, monkeypatch):
    monkeypatch.setenv("PAYMENTS_SIMULATE", "1")
    body = household_client.post(f"/bills/{bill.bill_id}/pay").json()
    assert body["status"] == "successful" and body["provider"] == "simulated"
    assert body["transaction_id"].startswith("SIM-")
    db.refresh(bill)
    assert bill.payment_status == "paid"
    again = household_client.post(f"/bills/{bill.bill_id}/pay").json()
    assert again["already_paid"] is True and again["transaction_id"] == body["transaction_id"]


def test_when_paying_with_momo_should_ask_mtn_then_mark_paid_once_it_succeeds(db, household_client, bill, mtn):
    mtn.statuses = ["PENDING", "SUCCESSFUL"]
    started = household_client.post(f"/bills/{bill.bill_id}/pay").json()
    assert started["status"] == "pending" and started["provider"] == "momo_sandbox" and started["currency"] == "EUR"
    sent = mtn.requests[0]
    payment = db.get(Payment, started["id"])
    assert sent["headers"]["X-Reference-Id"] == payment.reference_id
    assert sent["headers"]["X-Target-Environment"] == "sandbox"
    assert sent["json"]["payer"] == {"partyIdType": "MSISDN", "partyId": "250788000111"}
    assert sent["json"]["amount"] == "6460"

    assert household_client.get(f"/payments/{started['id']}").json()["status"] == "pending"
    db.refresh(bill)
    assert bill.payment_status == "unpaid"
    done = household_client.get(f"/payments/{started['id']}").json()
    assert done["status"] == "successful" and done["transaction_id"] == "987654321"
    db.refresh(bill)
    assert bill.payment_status == "paid"


def test_when_a_payment_is_pending_should_not_ask_mtn_twice(household_client, bill, mtn):
    mtn.statuses = ["PENDING"]
    first = household_client.post(f"/bills/{bill.bill_id}/pay").json()
    second = household_client.post(f"/bills/{bill.bill_id}/pay").json()
    assert second["id"] == first["id"] and len(mtn.requests) == 1


def test_when_the_payer_declines_should_record_why_and_allow_another_try(db, household_client, bill, mtn):
    mtn.statuses, mtn.reason = ["FAILED"], "Payer not found"
    started = household_client.post(f"/bills/{bill.bill_id}/pay").json()
    failed = household_client.get(f"/payments/{started['id']}").json()
    assert failed["status"] == "failed" and failed["reason"] == "Payer not found"
    db.refresh(bill)
    assert bill.payment_status == "unpaid"
    mtn.statuses, mtn.reason = ["SUCCESSFUL"], None
    retry = household_client.post(f"/bills/{bill.bill_id}/pay").json()
    assert retry["id"] != started["id"] and retry["status"] == "pending"


def test_when_mtn_refuses_the_request_should_fail_without_charging(db, household_client, bill, mtn):
    mtn.refuse_request = True
    body = household_client.post(f"/bills/{bill.bill_id}/pay").json()
    assert body["status"] == "failed" and "HTTP 500" in body["reason"]
    db.refresh(bill)
    assert bill.payment_status == "unpaid"


def test_when_mtn_never_answers_should_give_up_after_ten_minutes(db, household_client, bill, mtn):
    mtn.statuses = ["PENDING"]
    started = household_client.post(f"/bills/{bill.bill_id}/pay").json()
    payment = db.get(Payment, started["id"])
    payment.created_at = datetime.utcnow() - timedelta(minutes=11)
    db.commit()
    body = household_client.get(f"/payments/{started['id']}").json()
    assert body["status"] == "failed" and "no answer" in body["reason"]


def test_when_another_household_asks_should_not_show_the_payment(db, household_client, anon_client, bill):
    from support.factories import household_token

    started = household_client.post(f"/bills/{bill.bill_id}/pay").json()
    add_household(db, "MTR-OTHER", make_history([0.4] * 3), phone="+250788222333")
    other = {"Authorization": f"Bearer {household_token('+250788222333')}"}
    assert anon_client.get(f"/payments/{started['id']}", headers=other).status_code == 404
    assert anon_client.post(f"/bills/{bill.bill_id}/pay", headers=other).status_code == 404


def test_when_momo_api_is_not_set_up_should_ask_for_momo_pay_and_wait_for_an_officer(
        db, household_client, client, bill, monkeypatch):
    monkeypatch.setenv("MOMO_PAY_CODE", "123456")
    started = household_client.post(f"/bills/{bill.bill_id}/pay").json()
    assert started["provider"] == "momo_pay" and started["status"] == "pending"
    assert started["ussd_code"] == "*182*8*1*123456*6460#" and started["reference"] == str(bill.bill_id)
    assert household_client.post(f"/bills/{bill.bill_id}/pay").json()["id"] == started["id"]  # one attempt

    # Nothing is paid until the household gives the transaction ID and an officer confirms it.
    assert client.get("/api/payments/to-check").json() == []
    sent = household_client.post(f"/payments/{started['id']}/reference", json={"transaction_id": "MP2610291234"})
    assert sent.status_code == 200 and sent.json()["transaction_id"] == "MP2610291234"
    db.refresh(bill)
    assert bill.payment_status == "unpaid"
    waiting = client.get("/api/payments/to-check").json()
    assert [(w["id"], w["transaction_id"]) for w in waiting] == [(started["id"], "MP2610291234")]

    done = client.post(f"/api/payments/{started['id']}/confirm")
    assert done.status_code == 200 and done.json()["status"] == "successful"
    db.refresh(bill)
    assert bill.payment_status == "paid"
    assert client.get("/api/payments/to-check").json() == []


def test_when_an_officer_cannot_find_a_momo_pay_payment_should_decline_it_and_let_the_household_retry(
        db, household_client, client, bill):
    started = household_client.post(f"/bills/{bill.bill_id}/pay").json()
    assert started["ussd_code"] is None  # no merchant code configured
    household_client.post(f"/payments/{started['id']}/reference", json={"transaction_id": "WRONG123"})
    declined = client.post(f"/api/payments/{started['id']}/decline", json={"reason": "not in the MoMo statement"})
    assert declined.json()["status"] == "failed" and declined.json()["reason"] == "not in the MoMo statement"
    db.refresh(bill)
    assert bill.payment_status == "unpaid"
    assert household_client.post(f"/bills/{bill.bill_id}/pay").json()["id"] != started["id"]


def test_when_a_transaction_id_is_not_plausible_should_refuse_it(household_client, bill):
    started = household_client.post(f"/bills/{bill.bill_id}/pay").json()
    for bad in ["", "ab", "<script>", "x" * 41]:
        assert household_client.post(f"/payments/{started['id']}/reference", json={"transaction_id": bad}).status_code == 422
