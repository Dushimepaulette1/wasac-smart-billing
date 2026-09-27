from datetime import datetime
from fastapi import APIRouter, Depends, Form
from sqlalchemy.orm import Session

from database import get_db, Meter, Reading, Bill, _calculate_bill
from models.anomaly_detector import AnomalyDetector
from schemas import USSDRequest

router = APIRouter()
_anomaly_detector = AnomalyDetector()


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

    if submitted < meter.last_reading:
        return {
            "response": (
                f"END Error: Reading {submitted:.0f} is less than your last reading "
                f"{meter.last_reading:.0f}. Please recheck your meter and try again."
            )
        }

    consumption = submitted - meter.last_reading

    past_readings = (
        db.query(Reading)
        .filter(Reading.meter_id == meter.meter_id, Reading.validation_status == "valid")
        .order_by(Reading.submission_time.desc())
        .limit(12)
        .all()
    )
    history = [r.implied_consumption for r in past_readings if r.implied_consumption is not None]
    is_anomalous, anomaly_score = _anomaly_detector.check(consumption, history)

    bill_data = _calculate_bill(consumption)
    validation_status = "anomaly_flagged" if is_anomalous else "valid"

    new_reading = Reading(
        meter_id=meter.meter_id,
        submitted_value=submitted,
        implied_consumption=consumption,
        submission_method="ussd",
        anomaly_score=anomaly_score,
        validation_status=validation_status,
        submission_time=datetime.utcnow(),
    )
    db.add(new_reading)
    db.flush()

    new_bill = Bill(
        customer_id=customer.customer_id,
        reading_id=new_reading.reading_id,
        consumption_m3=consumption,
        tier1_units=bill_data["tier1_units"],
        tier2_units=bill_data["tier2_units"],
        tier3_units=bill_data["tier3_units"],
        tier4_units=bill_data["tier4_units"],
        tier1_amount=bill_data["tier1_amount"],
        tier2_amount=bill_data["tier2_amount"],
        tier3_amount=bill_data["tier3_amount"],
        tier4_amount=bill_data["tier4_amount"],
        service_charge=1000.0,
        amount_due=bill_data["total"],
        payment_status="unpaid",
        created_at=datetime.utcnow(),
    )
    db.add(new_bill)

    meter.last_reading = submitted
    meter.last_reading_date = datetime.utcnow()
    db.commit()

    flag_msg = "\n⚠ Unusual consumption detected. WASAC will verify." if is_anomalous else ""
    response = (
        f"END Reading received: {submitted:.0f} m3\n"
        f"Consumption: {consumption:.1f} m3\n"
        f"Bill: RWF {bill_data['total']:,.0f}{flag_msg}\n"
        f"Dial *225# to pay via Mobile Money."
    )
    return {"response": response}
