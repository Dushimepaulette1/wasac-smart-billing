"""Paying a bill, and staff checking payments. The rules are in app/services/payments.py.

    /bills/{id}/pay, /payments/{id}, /payments/{id}/reference     the household
    /api/payments/...                                             staff
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.api.deps import Access, household_access, require_role, require_staff
from app.db.session import get_db
from app.models import Bill, Customer, Payment, StaffUser
from app.schemas import PaymentDecline, PaymentOut, PaymentReconcile, PaymentReference, PaymentToCheck
from app.services.audit import record
from app.services.balance import bill_balance
from app.services.payments import (
    MOMO_PAY,
    PaymentError,
    confirm,
    decline,
    mark_reviewed,
    needs_reconciliation,
    pay_code,
    payments_paid_twice,
    reconcile,
    refresh,
    start_payment,
    submit_reference,
    ussd_code,
)

router = APIRouter()


@router.post("/bills/{bill_id}/pay", response_model=PaymentOut)
async def pay_bill(bill_id: int, db: Session = Depends(get_db), access: Access = Depends(household_access)):
    """Start paying a bill with MTN Mobile Money (simulated without MoMo keys). A pending answer means
    the payer has a PIN prompt on their phone: check GET /payments/{id} until it is final."""
    bill = db.query(Bill).filter(Bill.bill_id == bill_id).first()
    if not bill or not access.owns_customer(bill.customer_id):
        raise HTTPException(status_code=404, detail="Bill not found")
    if bill_balance(db, bill).settled:
        done = (db.query(Payment).filter(Payment.bill_id == bill_id, Payment.status == "successful")
                .order_by(Payment.id.desc()).first())
        out = PaymentOut.model_validate(done) if done else PaymentOut(
            id=0, bill_id=bill_id, provider="unknown", status="successful", amount=bill.amount_due, currency="RWF")
        return out.model_copy(update={"already_paid": True})
    customer = db.query(Customer).filter(Customer.customer_id == bill.customer_id).first()
    try:
        payment = await run_in_threadpool(start_payment, db, bill, customer.phone if customer else "")
    except PaymentError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    return payment_out(payment)


def payment_out(payment: Payment) -> PaymentOut:
    out = PaymentOut.model_validate(payment)
    if payment.provider == MOMO_PAY:
        out = out.model_copy(update={"ussd_code": ussd_code(payment.amount), "pay_code": pay_code(),
                                     "reference": str(payment.bill_id)})
    return out


@router.get("/payments/{payment_id}", response_model=PaymentOut)
async def get_payment(payment_id: int, db: Session = Depends(get_db), access: Access = Depends(household_access)):
    """Where a payment stands; a pending one is checked with MTN first."""
    payment = db.get(Payment, payment_id)
    bill = db.get(Bill, payment.bill_id) if payment else None
    if not payment or not bill or not access.owns_customer(bill.customer_id):
        raise HTTPException(status_code=404, detail="Payment not found")
    return payment_out(await run_in_threadpool(refresh, db, payment))


def _own_payment(db: Session, access: Access, payment_id: int) -> Payment:
    payment = db.get(Payment, payment_id)
    bill = db.get(Bill, payment.bill_id) if payment else None
    if not payment or not bill or not access.owns_customer(bill.customer_id):
        raise HTTPException(status_code=404, detail="Payment not found")
    return payment


@router.post("/payments/{payment_id}/reference", response_model=PaymentOut)
async def payment_reference(payment_id: int, body: PaymentReference, db: Session = Depends(get_db),
                            access: Access = Depends(household_access)):
    """After paying by MoMo Pay: the transaction ID from MTN's SMS. The bill stays unpaid until a
    WASAC officer finds the payment in WASAC's MoMo merchant account."""
    try:
        return payment_out(submit_reference(db, _own_payment(db, access, payment_id), body.transaction_id.strip()))
    except PaymentError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


# ---- Staff: checking MoMo Pay payments --------------------------------------

@router.get("/api/payments/to-check", response_model=List[PaymentToCheck])
async def payments_to_check(db: Session = Depends(get_db), _staff: StaffUser = Depends(require_staff)):
    """MoMo Pay payments with a transaction ID, waiting for an officer to find them in WASAC's MoMo
    merchant account, oldest first; then bills paid more than once in the last PAID_TWICE_DAYS days."""
    rows = (
        db.query(Payment, Bill, Customer)
        .join(Bill, Bill.bill_id == Payment.bill_id)
        .join(Customer, Customer.customer_id == Bill.customer_id)
        .filter(Payment.provider == MOMO_PAY, Payment.status == "pending", Payment.transaction_id.isnot(None))
        .order_by(Payment.updated_at.asc())
        .all()
    )
    return [
        PaymentToCheck(id=p.id, bill_id=b.bill_id, customer_id=c.customer_id, customer_name=c.name,
                       meter_id=c.meter_id, amount=p.amount, transaction_id=p.transaction_id,
                       created_at=p.created_at, submitted_at=p.updated_at)
        for p, b, c in rows
    ] + [
        PaymentToCheck(kind="paid_twice", id=p.id, bill_id=b.bill_id, customer_id=c.customer_id,
                       customer_name=c.name, meter_id=c.meter_id, amount=p.amount, transaction_id=p.transaction_id,
                       created_at=p.created_at, submitted_at=p.updated_at)
        for p, b, c in payments_paid_twice(db)
    ] + [
        PaymentToCheck(kind="needs_reconciliation", id=p.id, bill_id=b.bill_id, customer_id=c.customer_id,
                       customer_name=c.name, meter_id=c.meter_id, amount=p.amount, transaction_id=p.transaction_id,
                       created_at=p.created_at, submitted_at=p.updated_at, reason=p.reason)
        for p, b, c in needs_reconciliation(db)
    ]


@router.post("/api/payments/{payment_id}/recheck", response_model=PaymentOut)
async def recheck_payment(payment_id: int, db: Session = Depends(get_db), _staff: StaffUser = Depends(require_staff)):
    """Ask MTN again about an open attempt. Never sends a prompt."""
    payment = db.get(Payment, payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payment_out(await run_in_threadpool(refresh, db, payment))


@router.post("/api/payments/{payment_id}/reconcile", response_model=PaymentOut)
async def reconcile_payment(payment_id: int, body: PaymentReconcile, request: Request, db: Session = Depends(get_db),
                            staff: StaffUser = Depends(require_role("supervisor"))):
    """A supervisor settles an attempt from MTN's records, with the evidence (supervisors and admins)."""
    payment = db.get(Payment, payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    paid = body.outcome == "paid"
    try:
        payment = await run_in_threadpool(reconcile, db, payment, paid, body.evidence.strip(), body.transaction_id)
    except PaymentError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    record(db, staff.username, "payment_reconciled_paid" if paid else "payment_reconciled_failed",
           target=f"bill {payment.bill_id}", detail=f"RWF {payment.amount:,.0f}: {body.evidence.strip()}"[:200],
           request=request)
    return payment_out(payment)


@router.post("/api/payments/{payment_id}/reviewed", response_model=PaymentOut)
async def review_paid_twice(payment_id: int, request: Request, db: Session = Depends(get_db),
                            staff: StaffUser = Depends(require_staff)):
    """Staff have looked at a bill paid twice: off the list, still on record."""
    payment = db.get(Payment, payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    try:
        payment = mark_reviewed(db, payment, staff.username)
    except PaymentError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    record(db, staff.username, "paid_twice_reviewed", target=f"bill {payment.bill_id}",
           detail=f"RWF {payment.amount:,.0f}, {payment.transaction_id}", request=request)
    return payment_out(payment)


@router.post("/api/payments/{payment_id}/confirm", response_model=PaymentOut)
async def confirm_payment(payment_id: int, request: Request, db: Session = Depends(get_db),
                          staff: StaffUser = Depends(require_staff)):
    """The officer found the payment in WASAC's MoMo merchant account: the bill is paid."""
    payment = db.get(Payment, payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    try:
        payment = await run_in_threadpool(confirm, db, payment)
    except PaymentError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    record(db, staff.username, "payment_confirmed", target=f"bill {payment.bill_id}",
           detail=f"RWF {payment.amount:,.0f}, MoMo {payment.transaction_id}", request=request)
    return payment_out(payment)


@router.post("/api/payments/{payment_id}/decline", response_model=PaymentOut)
async def decline_payment(payment_id: int, body: PaymentDecline, request: Request, db: Session = Depends(get_db),
                          staff: StaffUser = Depends(require_staff)):
    """The officer could not find the payment: the household is told by SMS and can pay again."""
    payment = db.get(Payment, payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    try:
        payment = await run_in_threadpool(decline, db, payment, body.reason.strip())
    except PaymentError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    record(db, staff.username, "payment_declined", target=f"bill {payment.bill_id}",
           detail=f"MoMo {payment.transaction_id}: {body.reason.strip()}"[:200], request=request)
    return payment_out(payment)
