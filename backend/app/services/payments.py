"""Paying a bill, in one of three ways:

    momo        MTN Mobile Money API (app/services/momo.py), when its keys are set: MTN sends the
                payer a PIN prompt, and MTN's own answer marks the bill paid (refresh)
    momo_pay    otherwise: the household pays WASAC's MoMo Pay merchant code by USSD
                (MOMO_PAY_CODE, dialled as MOMO_PAY_USSD), then enters the transaction ID from
                MTN's SMS. The bill stays unpaid until a WASAC officer finds that payment in
                WASAC's MoMo merchant account and confirms it (confirm / decline)
    simulated   only with PAYMENTS_SIMULATE=1 (tests and demos): succeeds at once

    start_payment     reuse the open attempt, or start one
    refresh           ask MTN about a pending API attempt; mark paid (once, SMS receipt) or failed
    submit_reference  the household's MoMo transaction ID for a momo_pay attempt
    confirm / decline the officer's check of a momo_pay attempt

Never two prompts for one bill. A bill has at most one pending attempt (the bill row is locked
while one is started, and a partial unique index backs that up), and a new MTN prompt is only sent
once every earlier attempt has a final answer from MTN. An answer we are not sure of (a timeout
after sending, an MTN 5xx, no status yet) keeps the attempt pending: only MTN's status (success,
failure, or "no such request") ends it, however long that takes.
A momo_pay attempt waits for the officer, however long that takes.
"""
import os
import uuid
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Bill, Customer
from app.models.payment import FAILED, PENDING, SUCCESSFUL, Payment
from app.services import momo
from app.services.balance import bill_balance, settle
from app.services.sms import send_sms

# After this an attempt MTN has not settled is shown as still being confirmed (it stays pending).
PENDING_LIMIT = timedelta(minutes=10)
CONFIRMING = "confirming with MTN"
# Before this change an unanswered attempt was marked failed after 10 minutes without asking MTN;
# such attempts from the last day are asked about again before a new prompt is sent.
OLD_LOCAL_FAILURE = "no answer from MTN Mobile Money"
RECHECK_WINDOW = timedelta(hours=24)
MOMO_PAY = "momo_pay"
SIMULATED = "simulated"


def pay_code():
    """WASAC's MoMo Pay merchant code, or None when it is not set."""
    return os.getenv("MOMO_PAY_CODE", "").strip() or None


def ussd_code(amount: float):
    """What the household dials to pay, e.g. *182*8*1*123456*6460#. The format can be changed with
    MOMO_PAY_USSD (placeholders {code} and {amount}); None without a merchant code."""
    code = pay_code()
    if not code:
        return None
    template = os.getenv("MOMO_PAY_USSD", "*182*8*1*{code}*{amount}#")
    return template.format(code=code, amount=int(round(amount)))


class PaymentError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code, self.detail = status_code, detail


FINAL_FAILURES = {"FAILED", "REJECTED", "TIMEOUT", "EXPIRED", "CANCELLED"}
NOT_FOUND = "NOT_FOUND"
API_PROVIDERS = ("momo", "momo_sandbox")


def _lock_bill(db: Session, bill_id: int) -> Bill:
    return db.query(Bill).filter(Bill.bill_id == bill_id).with_for_update().populate_existing().one()


def _lock_payment(db: Session, payment_id: int) -> Payment:
    return db.query(Payment).filter(Payment.id == payment_id).with_for_update().populate_existing().one()


def _open_attempt(db: Session, bill_id: int) -> Optional[Payment]:
    return (
        db.query(Payment)
        .filter(Payment.bill_id == bill_id, Payment.status == PENDING)
        .order_by(Payment.id.desc())
        .first()
    )


def _mark_paid(db: Session, payment: Payment, bill: Bill, transaction_id: Optional[str]) -> None:
    """The payment succeeded. The bill is paid once (one SMS receipt); a second success on a paid
    bill is still recorded as successful, and staff see it as paid twice (payments_paid_twice)."""
    payment.status = SUCCESSFUL
    payment.transaction_id = transaction_id
    payment.updated_at = datetime.utcnow()
    if bill.payment_status != "paid":
        bill.payment_status = "paid"
        customer = db.query(Customer).filter(Customer.customer_id == bill.customer_id).first()
        if customer and customer.phone:
            send_sms(customer.phone, f"WASAC: payment of RWF {payment.amount:,.0f} received for bill {bill.bill_id}. "
                                     f"Ref {transaction_id or payment.reference_id[:8]}. Thank you.")
    settle(db, bill.customer_id)  # anything paid beyond the balance becomes credit


def _settle_old_failures(db: Session, bill: Bill) -> Optional[Payment]:
    """Ask MTN about this bill's attempts that were failed locally (not by MTN) in the last day.
    Returns the attempt if MTN says it succeeded (the bill is then paid). Raises PaymentError if
    MTN cannot be asked: a new prompt then waits, so a late success cannot be paid twice."""
    old = (
        db.query(Payment)
        .filter(Payment.bill_id == bill.bill_id, Payment.status == FAILED, Payment.reason == OLD_LOCAL_FAILURE,
                Payment.provider.in_(API_PROVIDERS), Payment.created_at > datetime.utcnow() - RECHECK_WINDOW)
        .all()
    )
    for payment in old:
        try:
            answer = momo.payment_status(payment.reference_id)
        except momo.MomoError:
            raise PaymentError(503, "We are still confirming an earlier payment with MTN. Try again in a few minutes.")
        if answer.status == "SUCCESSFUL":
            _mark_paid(db, payment, bill, answer.transaction_id)
            return payment
        if answer.status == "PENDING":
            raise PaymentError(409, "An earlier payment request is still open on your phone. "
                                    "Approve or cancel it, then try again.")
        payment.reason = (answer.reason or answer.status.lower())[:120]  # MTN's final word: not asked again
        payment.updated_at = datetime.utcnow()
    return None


def start_payment(db: Session, bill: Bill, phone: str) -> Payment:
    """Reuse the bill's open attempt, or start one. Commits. The attempt is committed before MTN is
    asked, so its reference id is kept even if the request then goes wrong."""
    bill = _lock_bill(db, bill.bill_id)
    owed = bill_balance(db, bill)
    if owed.settled:
        done = (db.query(Payment).filter(Payment.bill_id == bill.bill_id, Payment.status == SUCCESSFUL)
                .order_by(Payment.id.desc()).first())
        db.commit()
        if done:
            return done
        raise PaymentError(409, "This bill is already paid.")
    open_attempt = _open_attempt(db, bill.bill_id)
    if open_attempt:
        db.commit()
        return refresh(db, open_attempt)  # never ask MTN twice, never two MoMo Pay attempts

    configured = momo.momo_configured()
    if configured:
        try:
            settled = _settle_old_failures(db, bill)
        except PaymentError:
            db.rollback()
            raise
        if settled:
            db.commit()
            return settled
    simulate = not configured and os.getenv("PAYMENTS_SIMULATE", "0") == "1"
    payment = Payment(
        bill_id=bill.bill_id,
        provider=momo.provider_name() if configured else (SIMULATED if simulate else MOMO_PAY),
        reference_id=str(uuid.uuid4()),
        status=PENDING,
        amount=owed.outstanding,
        currency=momo.currency() if configured else "RWF",
    )
    db.add(payment)
    if simulate:
        db.flush()
        _mark_paid(db, payment, bill, f"SIM-{bill.bill_id:06d}-{payment.id}")
    try:
        db.commit()
    except IntegrityError:  # another request opened an attempt first (uq_payments_one_pending)
        db.rollback()
        existing = _open_attempt(db, bill.bill_id)
        if existing is None:
            raise
        return refresh(db, existing)
    if simulate or not configured:  # simulated: paid; MoMo Pay: wait for the household's transaction ID
        return payment

    try:
        momo.request_to_pay(payment.reference_id, payment.amount, phone, external_id=f"bill-{bill.bill_id}",
                            note=f"WASAC water bill {bill.bill_id}")
    except momo.MomoError as e:
        payment = _lock_payment(db, payment.id)
        if e.uncertain:  # MTN may have it: keep the attempt open and let MTN's status decide
            payment.reason = CONFIRMING
        else:
            payment.status, payment.reason = FAILED, str(e)[:120]
        payment.updated_at = datetime.utcnow()
        db.commit()
    return payment


def refresh(db: Session, payment: Payment) -> Payment:
    """Ask MTN how a pending API attempt ended. Only MTN's answer closes it. Commits."""
    if payment.status != PENDING or payment.provider in (SIMULATED, MOMO_PAY):
        return payment
    try:
        answer = momo.payment_status(payment.reference_id)
    except momo.MomoError:
        return payment  # ask again on the next check
    payment = _lock_payment(db, payment.id)
    if payment.status != PENDING:  # another request settled it meanwhile
        db.commit()
        return payment
    now = datetime.utcnow()
    if answer.status == "SUCCESSFUL":
        _mark_paid(db, payment, _lock_bill(db, payment.bill_id), answer.transaction_id)
    elif answer.status in FINAL_FAILURES:
        payment.status, payment.reason = FAILED, (answer.reason or answer.status.lower())[:120]
        payment.updated_at = now
    elif answer.status == NOT_FOUND:  # MTN never got the request: no prompt, safe to try again
        payment.status, payment.reason = FAILED, "MTN has no record of this payment request"
        payment.updated_at = now
    elif now - payment.created_at > PENDING_LIMIT and payment.reason != CONFIRMING:
        payment.reason, payment.updated_at = CONFIRMING, now
    db.commit()
    return payment


def submit_reference(db: Session, payment: Payment, transaction_id: str) -> Payment:
    """The household paid by MoMo Pay and types the transaction ID from MTN's SMS. Commits.
    One MTN transaction pays one bill: an ID already given for another payment is refused."""
    payment = _lock_payment(db, payment.id)
    if payment.provider != MOMO_PAY or payment.status != PENDING:
        db.rollback()
        raise PaymentError(409, "This payment is not waiting for a MoMo transaction ID.")
    used = (
        db.query(Payment.id)
        .filter(Payment.transaction_id == transaction_id, Payment.provider == MOMO_PAY,
                Payment.status != FAILED, Payment.id != payment.id)
        .first()
    )
    if used:
        db.rollback()
        raise PaymentError(409, "This transaction ID was already given for another payment. "
                                "Check the ID in MTN's SMS.")
    payment.transaction_id = transaction_id
    payment.updated_at = datetime.utcnow()
    try:
        db.commit()
    except IntegrityError:  # the same ID given at the same moment for another bill (uq_payments_momo_pay_txn)
        db.rollback()
        raise PaymentError(409, "This transaction ID was already given for another payment. "
                                "Check the ID in MTN's SMS.")
    return payment


def confirm(db: Session, payment: Payment) -> Payment:
    """An officer found this payment in WASAC's MoMo merchant account: the bill is paid. Commits.
    Locked, so two officers confirming at once mark it paid once."""
    payment = _lock_payment(db, payment.id)
    if payment.provider != MOMO_PAY or payment.status != PENDING or not payment.transaction_id:
        db.rollback()
        raise PaymentError(409, "Only a MoMo Pay payment with a transaction ID can be confirmed.")
    _mark_paid(db, payment, _lock_bill(db, payment.bill_id), payment.transaction_id)
    db.commit()
    return payment


def decline(db: Session, payment: Payment, reason: str) -> Payment:
    """An officer could not find this payment: the household is told and can try again. Commits."""
    payment = _lock_payment(db, payment.id)
    if payment.provider != MOMO_PAY or payment.status != PENDING:
        db.rollback()
        raise PaymentError(409, "Only a MoMo Pay payment waiting for a check can be declined.")
    payment.status, payment.reason, payment.updated_at = FAILED, reason[:120], datetime.utcnow()
    bill = db.get(Bill, payment.bill_id)
    customer = db.query(Customer).filter(Customer.customer_id == bill.customer_id).first() if bill else None
    db.commit()
    if customer and customer.phone:
        send_sms(customer.phone, f"WASAC: we could not find your MoMo payment ({payment.transaction_id or 'no ID'}) "
                                 f"for bill {bill.bill_id}. Please check the transaction ID and try again.")
    return payment


PAID_TWICE_DAYS = 90


def payments_paid_twice(db: Session) -> list:
    """(payment, bill, customer) for every successful payment after the first on the same bill, in
    the last PAID_TWICE_DAYS days: the household paid more than once and is owed the difference."""
    since = datetime.utcnow() - timedelta(days=PAID_TWICE_DAYS)
    rows = (
        db.query(Payment, Bill, Customer)
        .join(Bill, Bill.bill_id == Payment.bill_id)
        .join(Customer, Customer.customer_id == Bill.customer_id)
        .filter(Payment.status == SUCCESSFUL, Payment.updated_at > since)
        .order_by(Payment.bill_id, Payment.updated_at, Payment.id)
        .all()
    )
    seen, extra = set(), []
    for payment, bill, customer in rows:
        first = (db.query(Payment.id).filter(Payment.bill_id == bill.bill_id, Payment.status == SUCCESSFUL)
                 .order_by(Payment.updated_at, Payment.id).first())
        if first and first.id != payment.id and payment.id not in seen:
            seen.add(payment.id)
            extra.append((payment, bill, customer))
    return extra
