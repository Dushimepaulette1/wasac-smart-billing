from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.anomaly.statuses import NOT_CONFIRMED
from app.api.deps import Access, household_access, require_role, require_staff
from app.db.session import get_db
from app.models import Bill, BillAdjustment, BillCorrection, Customer, Meter, Payment, Reading, StaffUser
from app.models.bill_correction import APPLIED
from app.schemas import (
    CustomerInfo,
    HouseholdEdit,
    HouseholdImport,
    HouseholdImportResult,
    HouseholdImportRow,
    HouseholdIn,
    MeterCorrectionRequest,
    PaymentDecline,
    PaymentOut,
    PaymentReconcile,
    PaymentReference,
    PaymentToCheck,
)
from app.services.audit import record
from app.services.balance import available_credit, balances, bill_balance, current_consumption
from app.services.bill_corrections import measured_from_zero
from app.services.households import (
    DEMO_PREFIX,
    HouseholdError,
    add_household,
    check_fields,
    describe,
    edit_household,
    import_csv,
)
from app.services.meter_correction import CORRECTION, CorrectionError, correct_meter
from app.services.payments import (
    MOMO_PAY,
    PaymentError,
    mark_reviewed,
    needs_reconciliation,
    payments_paid_twice,
    reconcile,
    confirm,
    decline,
    pay_code,
    refresh,
    start_payment,
    submit_reference,
    ussd_code,
)
from app.services.reading_window import PENDING, TOO_SOON, reading_block

router = APIRouter()


def _customer_info(db: Session, c: Customer) -> CustomerInfo:
    meter = db.query(Meter).filter(Meter.meter_id == c.meter_id).first()

    past = (
        db.query(Reading)
        .filter(Reading.meter_id == c.meter_id, Reading.validation_status.notin_(NOT_CONFIRMED),
                Reading.submission_method != CORRECTION)
        .order_by(Reading.submission_time.desc())
        .limit(6)
        .all()
    )
    corrected = current_consumption(db, [r.reading_id for r in past])
    used = [v for v in (corrected.get(r.reading_id, r.implied_consumption) for r in past) if v]
    avg = sum(used) / len(used) if used else None
    anomaly_flagged = any(
        r.validation_status in ("anomaly_flagged", "pending_review")
        for r in (db.query(Reading)
                   .filter(Reading.meter_id == c.meter_id)
                   .order_by(Reading.submission_time.desc())
                   .limit(1)
                   .all())
    )

    block = reading_block(db, meter) if meter else None
    owed = [b for b in balances(db, c.customer_id).values() if not b.settled]
    return CustomerInfo(
        customer_id=c.customer_id,
        name=c.name,
        phone=c.phone,
        sector=c.sector,
        meter_id=c.meter_id,
        last_reading=meter.last_reading if meter else 0.0,
        last_reading_date=meter.last_reading_date if meter else None,
        avg_consumption=round(avg, 1) if avg else None,
        anomaly_flagged=anomaly_flagged,
        reading_pending=bool(block and block.reason == PENDING),
        next_reading_from=block.opens_on if block and block.reason == TOO_SOON else None,
        unpaid_count=len(owed),
        unpaid_amount=round(sum(b.outstanding for b in owed), 2),
        credit_available=available_credit(db, c.customer_id),
        serial_number=meter.serial_number if meter else None,
        is_demo=c.customer_id.startswith(DEMO_PREFIX),
    )


@router.get("/customers", response_model=list[CustomerInfo])
async def list_customers(db: Session = Depends(get_db), _staff: StaffUser = Depends(require_staff)):
    """Every household. Staff only."""
    return [_customer_info(db, c) for c in db.query(Customer).all()]


@router.post("/customers", response_model=CustomerInfo, status_code=201)
async def create_customer(
    body: HouseholdIn, request: Request, db: Session = Depends(get_db), staff: StaffUser = Depends(require_staff),
):
    """Add a household and its meter (any staff). The phone number can sign in straight away."""
    f, errors = check_fields(body.model_dump())
    if errors:
        raise HTTPException(status_code=422, detail=describe(errors))
    try:
        customer = add_household(db, f)
    except HouseholdError as e:
        db.rollback()
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    record(db, staff.username, "household_added", target=f.meter_id, detail=f.name, request=request, commit=False)
    db.commit()
    return _customer_info(db, customer)


@router.post("/customers/import", response_model=HouseholdImportResult)
async def import_customers(
    body: HouseholdImport, request: Request, db: Session = Depends(get_db),
    staff: StaffUser = Depends(require_role("supervisor")),
):
    """Preview a CSV of households, or save it (apply=true; only when no row has an error).
    Supervisors and admins."""
    try:
        result = import_csv(db, body.csv, apply=body.apply)
    except HouseholdError as e:
        db.rollback()
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    if result.applied:
        record(db, staff.username, "households_imported",
               detail=f"{result.count('new')} new, {result.count('update')} updated", request=request, commit=False)
        db.commit()
    else:
        db.rollback()
    return HouseholdImportResult(
        new=result.count("new"), update=result.count("update"), unchanged=result.count("unchanged"),
        error=result.count("error"), applied=result.applied,
        rows=[HouseholdImportRow(**vars(r)) for r in result.rows],
    )


@router.get("/customers/{customer_id}", response_model=CustomerInfo)
async def get_customer(customer_id: str, db: Session = Depends(get_db), access: Access = Depends(household_access)):
    """One household: its own account, or any for staff."""
    access.require_customer(customer_id)
    customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return _customer_info(db, customer)


@router.patch("/customers/{customer_id}", response_model=CustomerInfo)
async def update_customer(
    customer_id: str, body: HouseholdEdit, request: Request, db: Session = Depends(get_db),
    staff: StaffUser = Depends(require_staff),
):
    """Change a household's name, phone, sector or meter serial number (any staff)."""
    customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    f, errors = check_fields(body.model_dump(), new=False)
    if errors:
        raise HTTPException(status_code=422, detail=describe(errors))
    try:
        changed = edit_household(db, customer, f)
    except HouseholdError as e:
        db.rollback()
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    if changed:
        record(db, staff.username, "household_updated", target=customer.meter_id, detail=", ".join(changed),
               request=request, commit=False)
    db.commit()
    return _customer_info(db, customer)


@router.post("/customers/{customer_id}/meter-correction", response_model=CustomerInfo)
async def meter_correction(
    customer_id: str,
    body: MeterCorrectionRequest,
    request: Request,
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(require_role("supervisor")),
):
    """Set the meter's current reading (supervisors and admins). Logged in Activity."""
    customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
    meter = db.query(Meter).filter(Meter.meter_id == customer.meter_id).first() if customer else None
    if not meter:
        raise HTTPException(status_code=404, detail="Customer not found")
    old = meter.last_reading
    try:
        correct_meter(db, meter, body.reading_m3)
    except CorrectionError as e:
        db.rollback()
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    record(db, staff.username, "meter_corrected", target=meter.meter_id,
           detail=f"{old:.3f} -> {meter.last_reading:.3f} m3: {body.reason.strip()}", request=request, commit=False)
    db.commit()
    return _customer_info(db, customer)


@router.get("/customers/{customer_id}/bills")
async def customer_bills(customer_id: str, db: Session = Depends(get_db), access: Access = Depends(household_access)):
    access.require_customer(customer_id)
    customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    bills = (
        db.query(Bill)
        .filter(Bill.customer_id == customer_id)
        .order_by(Bill.created_at.desc())
        .limit(12)
        .all()
    )
    money = balances(db, customer_id)
    applied = (
        db.query(BillAdjustment, BillCorrection)
        .join(BillCorrection, BillCorrection.id == BillAdjustment.correction_id)
        .filter(BillAdjustment.bill_id.in_([b.bill_id for b in bills]), BillCorrection.status == APPLIED)
        .order_by(BillAdjustment.id).all()
    ) if bills else []
    volumes = current_consumption(db, [b.reading_id for b in bills])
    read = db.query(Reading).filter(Reading.reading_id.in_([b.reading_id for b in bills])).all() if bills else []
    values = {r.reading_id: r.effective_value for r in read}
    # Only the oldest bill can have been measured from nothing.
    first = bills[-1] if bills else None
    first_reading = db.get(Reading, first.reading_id) if first and first.reading_id else None
    unknown = {first.bill_id: measured_from_zero(db, first, first_reading)} if first_reading else {}
    # amount_due is the bill as issued. payment_status answers "is anything still owed?" (a bill can
    # be settled by credit, or owe more after a correction); the money fields show how.
    return [
        {
            "bill_id": b.bill_id,
            "reading_id": b.reading_id,
            "consumption_m3": b.consumption_m3,
            "amount_due": b.amount_due,
            "payment_status": "paid" if money[b.bill_id].settled else "unpaid",
            "created_at": b.created_at,
            "tariff_version": b.tariff_version,
            "consumption_current": volumes.get(b.reading_id, b.consumption_m3),
            "reading_m3": values.get(b.reading_id),
            "unknown_start": unknown.get(b.bill_id, False),
            "charges": money[b.bill_id].charges,
            "paid": round(money[b.bill_id].paid, 2),
            "credit_used": round(money[b.bill_id].credit_used, 2),
            "outstanding": money[b.bill_id].outstanding,
            "adjustments": [
                {"amount_delta": a.amount_delta, "consumption_after": a.consumption_after,
                 "reason": c.reason, "at": c.decided_at or c.created_at}
                for a, c in applied if a.bill_id == b.bill_id
            ],
        }
        for b in bills
    ]


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
