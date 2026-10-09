from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db, Meter
from anomaly.service import notify_household, submit_reading
from schemas import USSDRequest

router = APIRouter()


@router.post("/submit-ussd")
async def submit_ussd(body: USSDRequest, db: Session = Depends(get_db)):
    """
    USSD endpoint compatible with Africa's Talking callback format.
    Returns a USSD menu response string.
    """
    phone = body.phone_number.strip()
    raw_reading = body.reading_value.strip()

    # Find meter by phone number
    from database import Customer
    customer = db.query(Customer).filter(Customer.phone == phone).first()
    if not customer:
        return {"response": "END Sorry, your phone number is not registered. Call WASAC at 1580."}

    meter = db.query(Meter).filter(Meter.meter_id == customer.meter_id).first()
    if not meter:
        return {"response": "END No meter found for your account. Call WASAC at 1580."}

    try:
        submitted = float(raw_reading)
    except ValueError:
        return {"response": "END Invalid reading. Please enter numbers only, e.g. 00444"}

    sub = submit_reading(db, meter, customer.customer_id, submitted, method="ussd")
    actions = notify_household(db, sub.anomaly)
    anomaly = {**sub.anomaly.to_dict(), "actions": actions}

    if sub.bill is None:
        response = (
            f"END Reading received: {submitted:.0f} m3\n"
            f"It is being checked by WASAC before billing. We will SMS you."
        )
        return {"response": response, "anomaly": anomaly}

    flag_msg = f"\n{sub.anomaly.message_for_household}" if sub.anomaly.is_anomaly else ""
    response = (
        f"END Reading received: {submitted:.0f} m3\n"
        f"Consumption: {sub.consumption_m3:.1f} m3\n"
        f"Bill: RWF {sub.bill.amount_due:,.0f}{flag_msg}\n"
        f"Dial *225# to pay via Mobile Money."
    )
    return {"response": response, "anomaly": anomaly}
