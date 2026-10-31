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
        self.refuse_request = False  # or an HTTP status to answer the request to pay with
        self.request_error = None    # an httpx exception class to raise instead of answering
        self.known = None            # reference ids MTN knows; None = every one (else 404)
        self.unreachable = False     # status checks fail to connect

    def post(self, url, json=None, headers=None, auth=None, timeout=None):
        if url.endswith("/collection/token/"):
            return Response(200, {"access_token": "tok", "expires_in": 3600})
        if self.request_error is not None:
            if self.request_error is not momo.httpx.ConnectError:
                self.requests.append({"url": url, "json": json, "headers": headers})  # it left, then no answer
            raise self.request_error("boom")
        self.requests.append({"url": url, "json": json, "headers": headers})
        code = self.refuse_request if isinstance(self.refuse_request, int) and self.refuse_request is not True else 500
        return Response(code if self.refuse_request else 202, None)

    def get(self, url, headers=None, timeout=None):
        if self.unreachable:
            raise momo.httpx.ConnectError("down")
        if self.known is not None and url.rsplit("/", 1)[-1] not in self.known:
            return Response(404, None)
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
    mtn.refuse_request = 400  # a definite refusal: no prompt was sent
    body = household_client.post(f"/bills/{bill.bill_id}/pay").json()
    assert body["status"] == "failed" and "HTTP 400" in body["reason"]
    db.refresh(bill)
    assert bill.payment_status == "unpaid"


# Changed with the payment reliability work: an MTN 5xx used to fail the attempt at once and an
# unanswered attempt was failed after 10 minutes without asking MTN. Either could leave a live
# prompt behind and let the household be prompted (and charged) twice. Now only MTN's status ends it.
def test_when_mtn_errors_after_the_request_should_keep_it_open_until_mtn_says_how_it_ended(
        db, household_client, bill, mtn):
    mtn.refuse_request = 500
    body = household_client.post(f"/bills/{bill.bill_id}/pay").json()
    assert body["status"] == "pending" and body["reason"] == "confirming with MTN"
    mtn.refuse_request, mtn.known = False, set()  # MTN does not know the reference: not proof of no charge
    again = household_client.post(f"/bills/{bill.bill_id}/pay").json()
    assert again["id"] == body["id"] and again["status"] == "pending" and "staff check" in again["reason"]
    assert len(mtn.requests) == 1  # never a second prompt


def test_when_mtn_never_answers_should_keep_checking_and_never_prompt_twice(db, household_client, bill, mtn):
    mtn.statuses = ["PENDING"]
    started = household_client.post(f"/bills/{bill.bill_id}/pay").json()
    payment = db.get(Payment, started["id"])
    payment.created_at = datetime.utcnow() - timedelta(minutes=11)
    db.commit()
    body = household_client.get(f"/payments/{started['id']}").json()
    assert body["status"] == "pending" and body["reason"] == "confirming with MTN"
    again = household_client.post(f"/bills/{bill.bill_id}/pay").json()
    assert again["id"] == started["id"] and len(mtn.requests) == 1


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


def test_when_the_request_times_out_and_mtn_later_reports_success_should_mark_paid_without_a_second_prompt(
        db, household_client, bill, mtn):
    mtn.request_error = momo.httpx.ReadTimeout
    started = household_client.post(f"/bills/{bill.bill_id}/pay").json()
    assert started["status"] == "pending" and started["reason"] == "confirming with MTN"
    mtn.request_error, mtn.statuses = None, ["SUCCESSFUL"]
    again = household_client.post(f"/bills/{bill.bill_id}/pay").json()
    assert again["id"] == started["id"] and again["status"] == "successful"
    assert len(mtn.requests) == 1
    db.refresh(bill)
    assert bill.payment_status == "paid"


def test_when_mtn_cannot_be_reached_before_sending_should_fail_so_the_household_can_retry(
        db, household_client, bill, mtn):
    mtn.request_error = momo.httpx.ConnectError  # never left: certainly no prompt
    body = household_client.post(f"/bills/{bill.bill_id}/pay").json()
    assert body["status"] == "failed" and len(mtn.requests) == 0


def test_when_mtn_status_cannot_be_checked_should_stay_pending_and_not_prompt_again(db, household_client, bill, mtn):
    mtn.statuses = ["PENDING"]
    started = household_client.post(f"/bills/{bill.bill_id}/pay").json()
    mtn.unreachable = True
    assert household_client.get(f"/payments/{started['id']}").json()["status"] == "pending"
    assert household_client.post(f"/bills/{bill.bill_id}/pay").json()["id"] == started["id"]
    assert len(mtn.requests) == 1


def test_when_an_attempt_was_failed_locally_before_and_mtn_says_it_succeeded_should_mark_paid_not_prompt(
        db, household_client, bill, mtn):
    from app.services.payments import OLD_LOCAL_FAILURE

    old = Payment(bill_id=bill.bill_id, provider="momo_sandbox", reference_id="old-ref", status="failed",
                  amount=bill.amount_due, currency="EUR", reason=OLD_LOCAL_FAILURE)
    db.add(old)
    db.commit()
    mtn.statuses = ["SUCCESSFUL"]
    body = household_client.post(f"/bills/{bill.bill_id}/pay").json()
    assert body["id"] == old.id and body["status"] == "successful" and len(mtn.requests) == 0
    db.refresh(bill)
    assert bill.payment_status == "paid"


def test_when_an_old_local_failure_cannot_be_checked_should_refuse_a_new_prompt(db, household_client, bill, mtn):
    from app.services.payments import OLD_LOCAL_FAILURE

    db.add(Payment(bill_id=bill.bill_id, provider="momo_sandbox", reference_id="old-ref", status="failed",
                   amount=bill.amount_due, currency="EUR", reason=OLD_LOCAL_FAILURE))
    db.commit()
    mtn.unreachable = True
    r = household_client.post(f"/bills/{bill.bill_id}/pay")
    assert r.status_code == 503 and len(mtn.requests) == 0


def test_when_a_momo_pay_transaction_id_was_used_for_another_bill_should_refuse_it(db, household_client, bill):
    other = Bill(customer_id=bill.customer_id, consumption_m3=5, amount_due=2750.0, payment_status="unpaid")
    db.add(other)
    db.commit()
    first = household_client.post(f"/bills/{bill.bill_id}/pay").json()
    second = household_client.post(f"/bills/{other.bill_id}/pay").json()
    assert household_client.post(f"/payments/{first['id']}/reference",
                                 json={"transaction_id": "MP2610291234"}).status_code == 200
    r = household_client.post(f"/payments/{second['id']}/reference", json={"transaction_id": "MP2610291234"})
    assert r.status_code == 409 and "already given" in r.json()["detail"]


def test_when_a_declined_transaction_id_is_given_again_should_accept_it(db, household_client, client, bill):
    first = household_client.post(f"/bills/{bill.bill_id}/pay").json()
    household_client.post(f"/payments/{first['id']}/reference", json={"transaction_id": "MP2610291234"})
    client.post(f"/api/payments/{first['id']}/decline", json={"reason": "not found yet"})
    retry = household_client.post(f"/bills/{bill.bill_id}/pay").json()
    assert household_client.post(f"/payments/{retry['id']}/reference",
                                 json={"transaction_id": "MP2610291234"}).status_code == 200


def test_when_a_bill_is_paid_twice_should_show_it_to_staff(db, household_client, client, bill, mtn):
    mtn.statuses = ["PENDING"]
    first = household_client.post(f"/bills/{bill.bill_id}/pay").json()
    # A second success for the same bill (e.g. an old prompt approved late) is recorded, not lost.
    late = Payment(bill_id=bill.bill_id, provider="momo_sandbox", reference_id="late-ref", status="pending",
                   amount=bill.amount_due, currency="EUR")
    mtn.statuses = ["SUCCESSFUL"]
    assert household_client.get(f"/payments/{first['id']}").json()["status"] == "successful"
    db.add(late)
    db.commit()
    assert household_client.get(f"/payments/{late.id}").json()["status"] == "successful"
    listed = client.get("/api/payments/to-check").json()
    assert [(p["kind"], p["id"]) for p in listed] == [("paid_twice", late.id)]


def test_when_two_officers_confirm_the_same_momo_pay_payment_should_mark_it_paid_once(db, household_client, client, bill):
    started = household_client.post(f"/bills/{bill.bill_id}/pay").json()
    household_client.post(f"/payments/{started['id']}/reference", json={"transaction_id": "MP2610291234"})
    assert client.post(f"/api/payments/{started['id']}/confirm").status_code == 200
    assert client.post(f"/api/payments/{started['id']}/confirm").status_code == 409


def test_when_an_older_database_lacks_the_payment_indexes_should_add_them():
    from sqlalchemy import create_engine, inspect, text
    from sqlalchemy.pool import StaticPool

    from app.db.init_db import add_late_indexes

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE bills (bill_id INTEGER PRIMARY KEY, reading_id INTEGER)"))
        conn.execute(text("CREATE TABLE payments (id INTEGER PRIMARY KEY, bill_id INTEGER, provider VARCHAR, "
                          "status VARCHAR, transaction_id VARCHAR)"))
    add_late_indexes(engine)
    names = {i["name"] for i in inspect(engine).get_indexes("payments")}
    assert {"uq_payments_one_pending", "uq_payments_momo_pay_txn"} <= names


# ---- Staff reconciliation: attempts MTN cannot answer for --------------------------------------


@pytest.fixture
def stuck(db, household_client, bill, mtn):
    """An attempt over 10 minutes old that MTN answers 404 for."""
    mtn.statuses = ["PENDING"]
    payment_id = household_client.post(f"/bills/{bill.bill_id}/pay").json()["id"]
    payment = db.get(Payment, payment_id)
    payment.created_at = datetime.utcnow() - timedelta(minutes=30)
    db.commit()
    mtn.known = set()
    assert household_client.get(f"/payments/{payment_id}").json()["status"] == "pending"
    return payment_id


@pytest.fixture
def supervisor(db, anon_client):
    from support.factories import add_officer, staff_token

    return {"Authorization": f"Bearer {staff_token(add_officer(db, 'sup1', role='supervisor'))}"}


EVIDENCE = "Checked MoMo partner portal 2026-10-30, nothing under this reference"


def reconcile(c, payment_id, headers, **body):
    return c.post(f"/api/payments/{payment_id}/reconcile", headers=headers, json={"evidence": EVIDENCE, **body})


def test_when_an_attempt_is_stuck_should_be_listed_for_staff_and_never_retried(db, household_client, client, bill, mtn, stuck):
    listed = client.get("/api/payments/to-check").json()
    assert [(p["kind"], p["id"]) for p in listed] == [("needs_reconciliation", stuck)]
    assert "staff check" in listed[0]["reason"]
    for _ in range(3):
        assert household_client.post(f"/bills/{bill.bill_id}/pay").json()["id"] == stuck
    assert len(mtn.requests) == 1
    db.refresh(bill)
    assert bill.payment_status == "unpaid"


def test_when_mtn_cannot_be_reached_at_all_should_also_be_listed(db, household_client, client, bill, mtn):
    mtn.statuses = ["PENDING"]
    payment_id = household_client.post(f"/bills/{bill.bill_id}/pay").json()["id"]
    db.get(Payment, payment_id).created_at = datetime.utcnow() - timedelta(hours=5)
    db.commit()
    mtn.unreachable = True
    assert [p["id"] for p in client.get("/api/payments/to-check").json()] == [payment_id]


def test_when_a_supervisor_closes_a_stuck_attempt_should_allow_a_new_try_and_keep_the_evidence(
        db, household_client, anon_client, bill, mtn, stuck, supervisor):
    from app.models import StaffAction

    r = reconcile(anon_client, stuck, supervisor, outcome="failed")
    assert r.status_code == 200 and r.json()["status"] == "failed" and "closed by staff" in r.json()["reason"]
    row = db.query(StaffAction).filter(StaffAction.action == "payment_reconciled_failed").one()
    assert row.username == "sup1" and "partner portal" in row.detail
    retry = household_client.post(f"/bills/{bill.bill_id}/pay").json()  # still 404 for the old one
    assert retry["id"] != stuck and len(mtn.requests) == 2


def test_when_a_supervisor_confirms_a_stuck_attempt_should_mark_paid_once(db, anon_client, bill, mtn, stuck, supervisor):
    r = reconcile(anon_client, stuck, supervisor, outcome="paid", transaction_id="MTN123456")
    assert r.status_code == 200 and r.json()["status"] == "successful" and r.json()["transaction_id"] == "MTN123456"
    db.refresh(bill)
    assert bill.payment_status == "paid"
    assert reconcile(anon_client, stuck, supervisor, outcome="paid", transaction_id="MTN123456").status_code == 409


def test_when_confirming_without_a_transaction_id_should_refuse(anon_client, stuck, supervisor):
    assert reconcile(anon_client, stuck, supervisor, outcome="paid").status_code == 422


@pytest.mark.parametrize("evidence", ["", "short"])
def test_when_there_is_no_real_evidence_should_refuse(anon_client, stuck, supervisor, evidence):
    r = anon_client.post(f"/api/payments/{stuck}/reconcile", headers=supervisor, json={"outcome": "failed", "evidence": evidence})
    assert r.status_code == 422


def test_when_an_officer_tries_to_reconcile_should_refuse(client, stuck):
    assert client.post(f"/api/payments/{stuck}/reconcile", json={"outcome": "failed", "evidence": EVIDENCE}).status_code == 403


def test_when_mtn_says_success_while_closing_should_record_success_not_failure(db, anon_client, bill, mtn, stuck, supervisor):
    mtn.known, mtn.statuses = None, ["SUCCESSFUL"]
    r = reconcile(anon_client, stuck, supervisor, outcome="failed")
    assert r.status_code == 409 and "successful" in r.json()["detail"]
    assert db.get(Payment, stuck).status == "successful"


def test_when_mtn_still_shows_it_open_should_refuse_to_close_it(db, anon_client, mtn, stuck, supervisor):
    mtn.known, mtn.statuses = None, ["PENDING"]
    assert reconcile(anon_client, stuck, supervisor, outcome="failed").status_code == 409
    assert db.get(Payment, stuck).status == "pending"


def test_when_mtn_reports_failure_while_confirming_should_refuse_to_mark_paid(db, anon_client, bill, mtn, stuck, supervisor):
    mtn.known, mtn.statuses = None, ["FAILED"]
    assert reconcile(anon_client, stuck, supervisor, outcome="paid", transaction_id="MTN1").status_code == 409
    db.refresh(bill)
    assert db.get(Payment, stuck).status == "failed" and bill.payment_status == "unpaid"


def test_when_mtn_cannot_be_asked_should_let_the_supervisor_decide_on_evidence(db, anon_client, mtn, stuck, supervisor):
    mtn.unreachable = True
    assert reconcile(anon_client, stuck, supervisor, outcome="failed").status_code == 200


def test_when_a_staff_closed_attempt_later_shows_success_should_mark_paid_not_prompt(
        db, household_client, anon_client, bill, mtn, stuck, supervisor):
    reconcile(anon_client, stuck, supervisor, outcome="failed")
    mtn.known, mtn.statuses = None, ["SUCCESSFUL"]
    body = household_client.post(f"/bills/{bill.bill_id}/pay").json()
    assert body["id"] == stuck and body["status"] == "successful" and len(mtn.requests) == 1


def test_when_staff_recheck_should_ask_mtn_and_never_prompt(client, bill, mtn, stuck):
    r = client.post(f"/api/payments/{stuck}/recheck")
    assert r.status_code == 200 and r.json()["status"] == "pending" and len(mtn.requests) == 1


def test_when_an_old_local_failure_gets_a_404_should_not_prompt(db, household_client, bill, mtn):
    from app.services.payments import OLD_LOCAL_FAILURE

    db.add(Payment(bill_id=bill.bill_id, provider="momo_sandbox", reference_id="old-ref", status="failed",
                   amount=bill.amount_due, currency="EUR", reason=OLD_LOCAL_FAILURE))
    db.commit()
    mtn.known = set()
    assert household_client.post(f"/bills/{bill.bill_id}/pay").status_code == 503 and len(mtn.requests) == 0


def test_when_staff_review_a_paid_twice_payment_should_leave_the_list_and_stay_on_record(db, client, bill):
    bill.payment_status = "paid"
    for ref in ("one", "two"):
        db.add(Payment(bill_id=bill.bill_id, provider="momo_sandbox", reference_id=ref, status="successful",
                       amount=bill.amount_due, currency="EUR"))
    db.commit()
    listed = client.get("/api/payments/to-check").json()
    assert [p["kind"] for p in listed] == ["paid_twice"]
    assert client.post(f"/api/payments/{listed[0]['id']}/reviewed").status_code == 200
    assert client.get("/api/payments/to-check").json() == []
    assert db.get(Payment, listed[0]["id"]).status == "successful"


def test_when_a_bill_has_part_of_a_franc_should_record_what_mtn_collects(db, household_client, bill, mtn):
    bill.amount_due = 6460.5
    db.commit()
    body = household_client.post(f"/bills/{bill.bill_id}/pay").json()
    assert body["amount"] == 6461 and mtn.requests[0]["json"]["amount"] == "6461"
