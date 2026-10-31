"""What a household actually owes: the one definition of "unpaid" (bills.payment_status only says
a payment arrived). Nothing here changes a bill or a payment.

    charges      amount_due + applied adjustments
    paid         successful payments (old bills marked paid with no payment row: amount_due)
    credit_used  account credit spent on this bill
    credited_out overpayment on this bill already moved to the household's credit
    net          charges + credited_out - paid - credit_used
    outstanding  net when above zero; a net below zero is an overpayment, which settle moves to credit

Credits are applied by settle, oldest bill first, whenever a credit or a bill appears. A bill with a
payment in flight is skipped: the prompt is for the amount it showed.
"""
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Iterable, Optional

from fastapi import Request
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.models import Bill, Customer
from app.models.bill_correction import APPLIED, OVERPAYMENT, USED, AccountCredit, BillAdjustment, BillCorrection
from app.models.payment import MOMO_PAY, PENDING, SUCCESSFUL, Payment
from app.services.audit import record

SETTLED_BELOW = 0.5  # under half a franc: MoMo takes whole francs, so a bill can end on a remainder
SYSTEM = "system"


def in_flight():
    """Payment filter: money that may be moving. An MTN prompt, or a MoMo Pay payment with its
    transaction ID. A MoMo Pay attempt with no ID only means Pay was tapped: the household may never
    have paid, and such an attempt never expires, so it must not hold a bill's figures still."""
    return and_(Payment.status == PENDING, or_(Payment.provider != MOMO_PAY, Payment.transaction_id.isnot(None)))


@dataclass
class BillBalance:
    bill_id: int
    amount_due: float
    adjustments: float = 0.0
    paid: float = 0.0
    credit_used: float = 0.0
    credited_out: float = 0.0

    @property
    def charges(self) -> float:
        return round(self.amount_due + self.adjustments, 2)

    @property
    def net(self) -> float:
        return round(self.charges + self.credited_out - self.paid - self.credit_used, 2)

    @property
    def outstanding(self) -> float:
        return max(self.net, 0.0)

    @property
    def settled(self) -> bool:
        return self.outstanding < SETTLED_BELOW


def balances(db: Session, customer_id: str) -> Dict[int, BillBalance]:
    """Every bill of this household, oldest first."""
    bills = db.query(Bill).filter(Bill.customer_id == customer_id).order_by(Bill.created_at, Bill.bill_id).all()
    ids = [b.bill_id for b in bills]
    if not ids:
        return {}
    adjusted = dict(
        db.query(BillAdjustment.bill_id, func.sum(BillAdjustment.amount_delta))
        .join(BillCorrection, BillCorrection.id == BillAdjustment.correction_id)
        .filter(BillAdjustment.bill_id.in_(ids), BillCorrection.status == APPLIED)
        .group_by(BillAdjustment.bill_id).all()
    )
    paid = dict(
        db.query(Payment.bill_id, func.sum(Payment.amount))
        .filter(Payment.bill_id.in_(ids), Payment.status == SUCCESSFUL)
        .group_by(Payment.bill_id).all()
    )
    used, out = defaultdict(float), defaultdict(float)
    for credit in db.query(AccountCredit).filter(AccountCredit.customer_id == customer_id).all():
        if credit.kind == USED and credit.bill_id:
            used[credit.bill_id] -= credit.amount
        elif credit.kind == OVERPAYMENT and credit.source_bill_id:
            out[credit.source_bill_id] += credit.amount
    return {
        b.bill_id: BillBalance(
            bill_id=b.bill_id, amount_due=b.amount_due or 0.0, adjustments=adjusted.get(b.bill_id) or 0.0,
            # Bills marked paid before payments were recorded have no payment row.
            paid=paid.get(b.bill_id, b.amount_due if b.payment_status == "paid" else 0.0) or 0.0,
            credit_used=used[b.bill_id], credited_out=out[b.bill_id],
        )
        for b in bills
    }


def current_consumption(db: Session, reading_ids: Iterable[int]) -> Dict[int, float]:
    """reading_id -> the volume its bill stands at after corrections, for readings with a correction.
    The bill and reading keep the original figures; this is what to show alongside them."""
    ids = [i for i in reading_ids if i is not None]
    if not ids:
        return {}
    rows = (
        db.query(Bill.reading_id, BillAdjustment.consumption_after)
        .join(BillAdjustment, BillAdjustment.bill_id == Bill.bill_id)
        .join(BillCorrection, BillCorrection.id == BillAdjustment.correction_id)
        .filter(Bill.reading_id.in_(ids), BillCorrection.status == APPLIED)
        .order_by(BillAdjustment.id).all()
    )
    return dict(rows)  # the latest adjustment wins


def bill_balance(db: Session, bill: Bill) -> BillBalance:
    return balances(db, bill.customer_id)[bill.bill_id]


def available_credit(db: Session, customer_id: str) -> float:
    total = db.query(func.coalesce(func.sum(AccountCredit.amount), 0.0)).filter(
        AccountCredit.customer_id == customer_id).scalar()
    return round(float(total), 2)


def settle(db: Session, customer_id: Optional[str], actor: str = SYSTEM, request: Optional[Request] = None) -> None:
    """Move overpayments to credit and spend credit on outstanding bills, oldest first, with an audit
    row for each. Commits nothing. Call with the caller's rows flushed."""
    if not customer_id:
        return
    db.flush()
    # One at a time per household: two payments settling together must not spend one credit twice.
    db.query(Customer.customer_id).filter(Customer.customer_id == customer_id).with_for_update().first()
    for b in balances(db, customer_id).values():
        if b.net <= -0.01:
            db.add(AccountCredit(customer_id=customer_id, amount=-b.net, kind=OVERPAYMENT, source_bill_id=b.bill_id))
            record(db, actor, "credit_added", target=f"bill {b.bill_id}",
                   detail=f"{customer_id}: RWF {-b.net:,.2f} overpaid, kept as credit", request=request, commit=False)
    db.flush()
    available = available_credit(db, customer_id)
    if available < 0.01:
        return
    busy = {bill_id for (bill_id,) in db.query(Payment.bill_id).join(Bill, Bill.bill_id == Payment.bill_id).filter(
        Bill.customer_id == customer_id, in_flight()).all()}
    for b in balances(db, customer_id).values():
        if available < 0.01:
            break
        if b.bill_id in busy or b.outstanding < 0.01:
            continue
        use = round(min(available, b.outstanding), 2)
        db.add(AccountCredit(customer_id=customer_id, amount=-use, kind=USED, bill_id=b.bill_id))
        record(db, actor, "credit_applied", target=f"bill {b.bill_id}",
               detail=f"{customer_id}: RWF {use:,.2f} of credit used", request=request, commit=False)
        available = round(available - use, 2)
    db.flush()
