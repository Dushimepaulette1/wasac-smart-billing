import io
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from sqlalchemy.orm import Session

from database import get_db, Customer, Meter, _calculate_bill
from models.quality_gate import QualityGate
from models.crnn_model import CRNNReader
from anomaly.service import notify_household, submit_reading
from schemas import (
    AnomalyResultSchema,
    PhotoSubmitResponse,
    ConfirmReadingRequest,
    ConfirmReadingResponse,
    TariffBreakdown,
    BillCalculateRequest,
)

router = APIRouter()

_quality_gate = QualityGate()
_crnn_reader = CRNNReader()


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

    sub = submit_reading(db, meter, body.customer_id, submitted, method="camera")
    actions = notify_household(db, sub.anomaly)
    anomaly = AnomalyResultSchema(**sub.anomaly.to_dict(), actions=actions)

    if sub.bill is None:
        return ConfirmReadingResponse(
            success=True,
            consumption_m3=sub.consumption_m3,
            validation_status=sub.reading.validation_status,
            anomaly_flagged=True,
            anomaly_score=sub.anomaly.anomaly_score,
            anomaly=anomaly,
        )

    bill_data = _calculate_bill(sub.consumption_m3)
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

    return ConfirmReadingResponse(
        success=True,
        bill_amount=sub.bill.amount_due,
        consumption_m3=sub.consumption_m3,
        tariff_breakdown=breakdown,
        validation_status=sub.reading.validation_status,
        anomaly_flagged=sub.anomaly.is_anomaly,
        anomaly_score=sub.anomaly.anomaly_score,
        bill_id=sub.bill.bill_id,
        anomaly=anomaly,
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
