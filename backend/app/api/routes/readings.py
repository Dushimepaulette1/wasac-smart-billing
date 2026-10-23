from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.api.deps import Access, household_access, meter_for
from app.anomaly.location import PhotoEvidence
from app.db.session import get_db
from app.models import Customer
from app.services import billing
from app.services.photo_evidence import attach, save_photo_read
from app.utils.meter_value import parse_meter_value
from app.core.ratelimit import MAX_UPLOAD_BYTES
from app.anomaly.service import ReadingRefused, notify_household, submit_reading
from app.vision.image_io import BadImage
from app.vision.models import LOADED, ModelRegistry, get_registry
from app.vision.pipeline import analyze_photo, guide_frame
from app.schemas import (
    AnomalyResultSchema,
    GuideFrameResponse,
    PhotoSubmitResponse,
    ConfirmReadingRequest,
    ConfirmReadingResponse,
    TariffBreakdown,
    BillCalculateRequest,
)

router = APIRouter()

MAX_PHOTO_BYTES = MAX_UPLOAD_BYTES  # 10 MB; ratelimit.upload_guard refuses larger ones earlier
MAX_FRAME_BYTES = 2 * 1024 * 1024


async def _read_upload(file: UploadFile, limit: int) -> bytes:
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(status_code=413, detail=f"Image larger than {limit // (1024 * 1024)} MB")
    if not data:
        raise HTTPException(status_code=422, detail="Empty upload")
    return data


@router.post("/submit-photo", response_model=PhotoSubmitResponse)
async def submit_photo(
    file: UploadFile = File(...),
    models: ModelRegistry = Depends(get_registry),
    db: Session = Depends(get_db),
    access: Access = Depends(household_access),
):
    """Read a meter photo. Guidance codes never block; offer_manual_entry means no reading is suggested.
    The photo is kept for the officer who may check the reading (app/services/photo_evidence.py)."""
    data = await _read_upload(file, MAX_PHOTO_BYTES)
    try:
        result = await run_in_threadpool(analyze_photo, data, models, models.guidance_config())
    except BadImage as e:
        raise HTTPException(status_code=422, detail=str(e))
    used = ", ".join(s.detail for s in models.status.values() if s.state == LOADED)
    photo_id = save_photo_read(db, access.owner, result, used)
    payload = result.to_dict()
    payload.pop("measurements")
    return PhotoSubmitResponse(
        photo_id=photo_id,
        status="readable" if result.reading_digits else "unreadable",
        predicted_reading=result.raw_digits,
        confidence=result.confidence_min,
        quality_gate_score=result.quality_score,
        **payload,
    )


@router.post("/guide-frame", response_model=GuideFrameResponse)
async def guide_frame_route(
    file: UploadFile = File(...),
    models: ModelRegistry = Depends(get_registry),
    _access: Access = Depends(household_access),
):
    """Live framing hints for a small camera frame (640 px max): YOLO plus brightness/glare/blur."""
    data = await _read_upload(file, MAX_FRAME_BYTES)
    try:
        result = await run_in_threadpool(guide_frame, data, models, models.guidance_config())
    except BadImage as e:
        raise HTTPException(status_code=422, detail=str(e))
    return GuideFrameResponse(**result.to_dict())


@router.post("/confirm-reading", response_model=ConfirmReadingResponse)
async def confirm_reading(
    body: ConfirmReadingRequest,
    db: Session = Depends(get_db),
    access: Access = Depends(household_access),
):
    """A household confirms its reading (or staff enter one). A household's photo location is
    checked against the meter's (app/anomaly/location.py); staff readings are not."""
    meter = meter_for(db, access, body.meter_id)
    access.require_customer(body.customer_id)
    customer = db.query(Customer).filter(Customer.customer_id == body.customer_id).first()
    if not customer or customer.meter_id != meter.meter_id:
        raise HTTPException(status_code=404, detail="Meter not found")

    submitted = parse_meter_value(body.confirmed_reading)
    if submitted is None:
        raise HTTPException(status_code=422, detail="Reading must be a number like 00565.846")

    evidence = None
    if access.staff is None:
        where = body.location
        evidence = PhotoEvidence(
            photo_source=body.photo_source,
            lat=where.lat if where else None,
            lng=where.lng if where else None,
            accuracy_m=where.accuracy_m if where else None,
        )
    try:
        sub = submit_reading(db, meter, body.customer_id, submitted, method="camera", evidence=evidence,
                             household=access.staff is None)
    except ReadingRefused as refused:
        # 409: the app shows its own words for a block's reason (see GET /customers/{id}).
        raise HTTPException(status_code=409, detail=refused.message)
    attach(db, body.photo_id, access.owner, sub.reading, f"{round(submitted * 1000):08d}")
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

    bill_data = billing.calculate_bill(sub.consumption_m3)
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
    data = billing.calculate_bill(body.consumption_m3)
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
