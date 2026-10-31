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

    reconcile         a supervisor settles an attempt MTN cannot answer for, with evidence

Never two prompts for one bill. A bill has at most one pending attempt (the bill row is locked
while one is started, and a partial unique index backs that up), and a new MTN prompt is only sent
once every earlier attempt is finished. Only MTN's success or failure status finishes an attempt
by itself. An answer we are not sure of (a timeout after sending, an MTN 5xx, no status yet, or a
404: MTN does not know the reference, which is not proof of no charge) keeps it pending. After
PENDING_LIMIT it is on the staff Payments page: a supervisor who has looked in MTN's records closes
it, with the evidence in the audit log. MTN's status can overrule that, never the other way round.
A momo_pay attempt waits for the officer, however long that takes.
"""
import os
import uuid
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Bill, Customer
from app.models.payment import FAILED, MOMO_PAY, PENDING, SUCCESSFUL, Payment
from app.services import momo
from app.services.balance import bill_balance, settle
from app.services.billing import whole_francs
from app.services.sms import send_sms

# After this an attempt MTN has not settled is shown as still being confirmed (it stays pending).
PENDING_LIMIT = timedelta(minutes=10)
CONFIRMING = "confirming with MTN"
# Before this change an unanswered attempt was marked failed after 10 minutes without asking MTN;
# such attempts from the last day are asked about again before a new prompt is sent.
OLD_LOCAL_FAILURE = "no answer from MTN Mobile Money"
RECHECK_WINDOW = timedelta(hours=24)
NO_RECORD = "MTN has no record yet: a staff check is needed"
CLOSED_BY_STAFF = "closed by staff: "
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
    return template.format(code=code, amount=whole_francs(amount))


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
    """The payment succeeded. Every payment of money owed gets an SMS receipt, including the
    difference after a correction raised a paid bill. A success when nothing was owed is still
    recorded, gets no receipt, and staff see it as paid twice (payments_paid_twice)."""
    owed = not bill_balance(db, bill).settled
    payment.status = SUCCESSFUL
    payment.transaction_id = transaction_id
    payment.updated_at = datetime.utcnow()
    bill.payment_status = "paid"
    if owed:
        customer = db.query(Customer).filter(Customer.customer_id == bill.customer_id).first()
        if customer and customer.phone:
            send_sms(customer.phone, f"WASAC: payment of RWF {payment.amount:,.0f} received for bill {bill.bill_id}. "
                                     f"Ref {transaction_id or payment.reference_id[:8]}. Thank you.")
    settle(db, bill.customer_id)  # anything paid beyond the balance becomes credit


def _settle_old_failures(db: Session, bill: Bill) -> Optional[Payment]:
    """Ask MTN about this bill's attempts that were closed here, not by MTN, in the last day (old
    local failures and staff closures). Returns the attempt if MTN says it succeeded (the bill is
    then paid). Raises PaymentError if that cannot be ruled out: a new prompt then waits, so a late
    success cannot be paid twice. A staff closure stands on a 404: staff saw MTN's records."""
    old = (
        db.query(Payment)
        .filter(Payment.bill_id == bill.bill_id, Payment.status == FAILED,
                or_(Payment.reason == OLD_LOCAL_FAILURE, Payment.reason.like(f"{CLOSED_BY_STAFF}%")),
                Payment.provider.in_(API_PROVIDERS), Payment.created_at > datetime.utcnow() - RECHECK_WINDOW)
        .all()
    )
    for payment in old:
        staff_closed = payment.reason.startswith(CLOSED_BY_STAFF)
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
        if answer.status == NOT_FOUND:
            if staff_closed:
                continue
            raise PaymentError(503, "We are still confirming an earlier payment with MTN. Try again later.")
        payment.reason = (answer.reason or answer.status.lower())[:120]  # MTN's final word: not asked again
        payment.updated_at = datetime.utcnow()
    return None


def start_payment(db: Session, bill: Bill, phone: str) -> Payment:
    """Reuse the bill's open attempt, or start one. Commits. The attempt is committed before MTN is
    asked, so its reference id is kept even if the request then goes wrong."""
    bill = _lock_bill(db, bill.bill_id)
    settle(db, bill.customer_id)  # credit held back while an earlier attempt was open
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
        if open_attempt.provider == MOMO_PAY and not open_attempt.transaction_id:
            open_attempt.amount = whole_francs(owed.outstanding)  # not paid yet: show today's balance
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
        amount=whole_francs(owed.outstanding),  # what is actually collected, so the record matches MTN's
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
    elif answer.status == NOT_FOUND:  # not proof of no charge: stays open, a supervisor decides
        if payment.reason != NO_RECORD:
            payment.reason, payment.updated_at = NO_RECORD, now
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
ROUNDING = 1.0  # payments are whole francs, so a bill can end a few cents overpaid: that is not paying twice


def payments_paid_twice(db: Session) -> list:
    """(payment, bill, customer) for every successful payment after the first on a bill that ended
    up overpaid, in the last PAID_TWICE_DAYS days: the extra is now credit. A second payment that a
    correction called for (the bill went up) is not listed."""
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
        if payment.reviewed_at is not None:
            continue
        first = (db.query(Payment.id).filter(Payment.bill_id == bill.bill_id, Payment.status == SUCCESSFUL)
                 .order_by(Payment.updated_at, Payment.id).first())
        owed = bill_balance(db, bill)
        overpaid = owed.paid + owed.credit_used - owed.charges >= ROUNDING
        if overpaid and first and first.id != payment.id and payment.id not in seen:
            seen.add(payment.id)
            extra.append((payment, bill, customer))
    return extra


def mark_reviewed(db: Session, payment: Payment, staff: str) -> Payment:
    """Staff have looked at a paid-twice payment. It stays on record; the extra is already credit. Commits."""
    payment = _lock_payment(db, payment.id)
    if payment.status != SUCCESSFUL:
        db.rollback()
        raise PaymentError(409, "Only a successful payment can be marked as reviewed.")
    payment.reviewed_by, payment.reviewed_at = staff, datetime.utcnow()
    db.commit()
    return payment


def needs_reconciliation(db: Session) -> list:
    """(payment, bill, customer) for API attempts MTN has not settled after PENDING_LIMIT, oldest first."""
    return (
        db.query(Payment, Bill, Customer)
        .join(Bill, Bill.bill_id == Payment.bill_id)
        .join(Customer, Customer.customer_id == Bill.customer_id)
        .filter(Payment.provider.in_(API_PROVIDERS), Payment.status == PENDING,
                Payment.created_at < datetime.utcnow() - PENDING_LIMIT)
        .order_by(Payment.created_at.asc())
        .all()
    )


def reconcile(db: Session, payment: Payment, paid: bool, evidence: str, transaction_id: Optional[str] = None) -> Payment:
    """A supervisor settles an attempt from MTN's own records (partner portal, statement, support).
    MTN's live answer comes first: a status that contradicts the decision refuses it, and a final
    status settles the attempt as MTN says. Only "cannot be asked" or a 404 leaves it to the
    supervisor. Commits; the caller writes the audit row with the evidence."""
    if payment.provider not in API_PROVIDERS or payment.status != PENDING:
        raise PaymentError(409, "Only an open MTN payment can be reconciled.")
    if paid and not transaction_id:
        raise PaymentError(422, "Give MTN's transaction ID.")
    try:
        answer = momo.payment_status(payment.reference_id)
    except momo.MomoError:
        answer = None
    if answer is not None and answer.status not in (NOT_FOUND,):
        refresh(db, payment)
        db.refresh(payment)
        if answer.status == "PENDING":
            raise PaymentError(409, "MTN still shows this payment as open. Wait for it to finish.")
        raise PaymentError(409, f"MTN answered: it is {payment.status}. It has been recorded as MTN says.")
    payment = _lock_payment(db, payment.id)
    if payment.status != PENDING:
        db.rollback()
        raise PaymentError(409, "This payment has just been settled.")
    if paid:
        used = db.query(Payment.id).filter(Payment.transaction_id == transaction_id, Payment.id != payment.id).first()
        if used:
            db.rollback()
            raise PaymentError(409, "This transaction ID is already on another payment.")
        _mark_paid(db, payment, _lock_bill(db, payment.bill_id), transaction_id)
    else:
        payment.status, payment.reason = FAILED, f"{CLOSED_BY_STAFF}{evidence}"[:120]
        payment.updated_at = datetime.utcnow()
    db.commit()
    return payment
