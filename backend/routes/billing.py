from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db, Customer, Bill, Reading, Meter
from schemas import CustomerInfo

router = APIRouter()


@router.get("/customers", response_model=list[CustomerInfo])
async def list_customers(db: Session = Depends(get_db)):
    customers = db.query(Customer).all()
    result = []
    for c in customers:
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
            r.validation_status == "anomaly_flagged"
            for r in (db.query(Reading)
                       .filter(Reading.meter_id == c.meter_id)
                       .order_by(Reading.submission_time.desc())
                       .limit(1)
                       .all())
        )

        result.append(CustomerInfo(
            customer_id=c.customer_id,
            name=c.name,
            phone=c.phone,
            sector=c.sector,
            meter_id=c.meter_id,
            last_reading=meter.last_reading if meter else 0.0,
            last_reading_date=meter.last_reading_date if meter else None,
            avg_consumption=round(avg, 1) if avg else None,
            anomaly_flagged=anomaly_flagged,
        ))
    return result


@router.get("/customers/{customer_id}/bills")
async def customer_bills(customer_id: str, db: Session = Depends(get_db)):
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
async def pay_bill(bill_id: int, db: Session = Depends(get_db)):
    bill = db.query(Bill).filter(Bill.bill_id == bill_id).first()
    if not bill:
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
