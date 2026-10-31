"""Households and their bills. Paying them is in app/api/routes/payments.py."""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.anomaly.statuses import NOT_CONFIRMED
from app.api.deps import Access, household_access, require_role, require_staff
from app.db.session import get_db
from app.models import Bill, BillAdjustment, BillCorrection, Customer, Meter, Reading, StaffUser
from app.models.bill_correction import APPLIED
from app.schemas import (
    CustomerInfo,
    HouseholdEdit,
    HouseholdImport,
    HouseholdImportResult,
    HouseholdImportRow,
    HouseholdIn,
    MeterCorrectionRequest,
)
from app.services.audit import record
from app.services.balance import available_credit, balances, current_consumption
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
