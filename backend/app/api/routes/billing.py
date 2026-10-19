from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import Access, household_access
from app.models import StaffUser
from app.api.deps import require_staff
from app.db.session import get_db
from app.models import Bill, Customer, Meter, Reading
from app.schemas import CustomerInfo

router = APIRouter()


def _customer_info(db: Session, c: Customer) -> CustomerInfo:
    meter = db.query(Meter).filter(Meter.meter_id == c.meter_id).first()

    past = (
        db.query(Reading)
        .filter(Reading.meter_id == c.meter_id, Reading.validation_status == "valid")
        .order_by(Reading.submission_time.desc())
        .limit(6)
        .all()
    )
    avg = (
        sum(r.implied_consumption for r in past if r.implied_consumption) / len(past)
        if past else None
    )
    anomaly_flagged = any(
        r.validation_status in ("anomaly_flagged", "pending_review")
        for r in (db.query(Reading)
                   .filter(Reading.meter_id == c.meter_id)
                   .order_by(Reading.submission_time.desc())
                   .limit(1)
                   .all())
    )

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
    )


@router.get("/customers", response_model=list[CustomerInfo])
async def list_customers(db: Session = Depends(get_db), _staff: StaffUser = Depends(require_staff)):
    """Every household. Staff only."""
    return [_customer_info(db, c) for c in db.query(Customer).all()]


@router.get("/customers/{customer_id}", response_model=CustomerInfo)
async def get_customer(customer_id: str, db: Session = Depends(get_db), access: Access = Depends(household_access)):
    """One household: its own account, or any for staff."""
    access.require_customer(customer_id)
    customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
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
    return [
        {
            "bill_id": b.bill_id,
            "consumption_m3": b.consumption_m3,
            "amount_due": b.amount_due,
            "payment_status": b.payment_status,
            "created_at": b.created_at,
        }
        for b in bills
    ]


@router.post("/bills/{bill_id}/pay")
async def pay_bill(bill_id: int, db: Session = Depends(get_db), access: Access = Depends(household_access)):
    bill = db.query(Bill).filter(Bill.bill_id == bill_id).first()
    if not bill or not access.owns_customer(bill.customer_id):
        raise HTTPException(status_code=404, detail="Bill not found")
    if bill.payment_status == "paid":
        return {"message": "Bill already paid", "bill_id": bill_id}

    bill.payment_status = "paid"
    db.commit()
    return {
        "success": True,
        "bill_id": bill_id,
        "transaction_id": f"MOMO-{bill_id:06d}-RW",
        "amount_paid": bill.amount_due,
        "message": "Payment successful",
    }
