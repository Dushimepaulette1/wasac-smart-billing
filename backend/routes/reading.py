import io
from datetime import datetime
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from sqlalchemy.orm import Session

from database import get_db, Customer, Meter, Reading, Bill, _calculate_bill
from models.quality_gate import QualityGate
from models.crnn_model import CRNNReader
from models.anomaly_detector import AnomalyDetector
from schemas import (
    PhotoSubmitResponse,
    ConfirmReadingRequest,
    ConfirmReadingResponse,
    TariffBreakdown,
    BillCalculateRequest,
)

router = APIRouter()

_quality_gate = QualityGate()
_crnn_reader = CRNNReader()
_anomaly_detector = AnomalyDetector()


@router.post("/submit-photo", response_model=PhotoSubmitResponse)
async def submit_photo(file: UploadFile = File(...)):
    contents = await file.read()
    status, confidence, guidance = _quality_gate.predict_from_bytes(contents)

    if status == "unreadable":
        return PhotoSubmitResponse(
            status="unreadable",
            quality_gate_score=round(confidence, 3),
            guidance_message=guidance or (
                "Unable to read the meter. Please clean the glass, "
                "move closer, and ensure good lighting."
            ),
        )

    reading_str, crnn_conf = _crnn_reader.predict(contents)

    return PhotoSubmitResponse(
        status="readable",
        predicted_reading=reading_str,
        confidence=round(crnn_conf, 3),
        quality_gate_score=round(confidence, 3),
    )


@router.post("/confirm-reading", response_model=ConfirmReadingResponse)
async def confirm_reading(body: ConfirmReadingRequest, db: Session = Depends(get_db)):
    meter = db.query(Meter).filter(Meter.meter_id == body.meter_id).first()
    if not meter:
        raise HTTPException(status_code=404, detail="Meter not found")

    try:
        submitted = float(body.confirmed_reading)
    except ValueError:
        raise HTTPException(status_code=422, detail="Reading must be a number")

    if submitted < meter.last_reading:
        return ConfirmReadingResponse(
            success=False,
            validation_status="rejected",
            error_message=(
                f"Submitted reading {submitted} is less than the last recorded "
                f"reading {meter.last_reading}. Please check and re-enter."
            ),
        )

    consumption = submitted - meter.last_reading

    # Pull historical consumptions for anomaly check
    past_readings = (
        db.query(Reading)
        .filter(Reading.meter_id == body.meter_id, Reading.validation_status == "valid")
        .order_by(Reading.submission_time.desc())
        .limit(12)
        .all()
    )
    history = [r.implied_consumption for r in past_readings if r.implied_consumption is not None]

    is_anomalous, anomaly_score = _anomaly_detector.check(consumption, history)

    bill_data = _calculate_bill(consumption)
    breakdown = TariffBreakdown(
        tier1_units=bill_data["tier1_units"],
        tier1_amount=bill_data["tier1_amount"],
        tier2_units=bill_data["tier2_units"],
        tier2_amount=bill_data["tier2_amount"],
        tier3_units=bill_data["tier3_units"],
        tier3_amount=bill_data["tier3_amount"],
        tier4_units=bill_data["tier4_units"],
        tier4_amount=bill_data["tier4_amount"],
        service_charge=bill_data["service_charge"],
        total=bill_data["total"],
    )

    validation_status = "anomaly_flagged" if is_anomalous else "valid"

    new_reading = Reading(
        meter_id=body.meter_id,
        submitted_value=submitted,
        implied_consumption=consumption,
        submission_method="camera",
        anomaly_score=anomaly_score,
        validation_status=validation_status,
        submission_time=datetime.utcnow(),
    )
    db.add(new_reading)
    db.flush()

    new_bill = Bill(
        customer_id=body.customer_id,
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
    db.refresh(new_bill)

    return ConfirmReadingResponse(
        success=True,
        bill_amount=bill_data["total"],
        consumption_m3=consumption,
        tariff_breakdown=breakdown,
        validation_status=validation_status,
        anomaly_flagged=is_anomalous,
        anomaly_score=anomaly_score,
        bill_id=new_bill.bill_id,
    )


@router.post("/calculate-bill")
async def calculate_bill(body: BillCalculateRequest):
    if body.consumption_m3 < 0:
        raise HTTPException(status_code=422, detail="Consumption cannot be negative")
    data = _calculate_bill(body.consumption_m3)
    return {
        "consumption_m3": body.consumption_m3,
        "breakdown": {
            "tier1": {"units": data["tier1_units"], "rate_rwf": 350, "amount": data["tier1_amount"]},
            "tier2": {"units": data["tier2_units"], "rate_rwf": 530, "amount": data["tier2_amount"]},
            "tier3": {"units": data["tier3_units"], "rate_rwf": 791, "amount": data["tier3_amount"]},
            "tier4": {"units": data["tier4_units"], "rate_rwf": 1000, "amount": data["tier4_amount"]},
        },
        "service_charge": data["service_charge"],
        "total_amount_due": data["total"],
        "currency": "RWF",
    }
