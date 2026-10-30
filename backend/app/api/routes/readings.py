from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, File, Request, UploadFile, HTTPException
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.api.deps import Access, household_access, meter_for
from app.anomaly.location import PhotoEvidence
from app.db.session import get_db
from app.anomaly.notifications import message_for
from app.anomaly.rules import AnomalyType
from app.anomaly.statuses import READING_PENDING, READING_REJECTED
from app.models import AnomalyFlag, Bill, Customer, PhotoRead, Reading
from app.services import billing
from app.services.audit import record
from app.services.photo_evidence import claim, save_photo_read
from app.utils.meter_value import parse_meter_value
from app.core.ratelimit import MAX_UPLOAD_BYTES
from app.anomaly.service import ReadingRefused, evaluate_reading, notify_household, review_reason, submit_reading
from app.vision.image_io import BadImage
from app.vision.models import LOADED, ModelRegistry, get_registry
from app.vision.pipeline import analyze_photo, guide_frame
from app.schemas import (
    AnomalyResultSchema,
    GuideFrameResponse,
    PhotoSubmitResponse,
    ConfirmReadingRequest,
    ConfirmReadingResponse,
    ReadingCheckResponse,
    TariffBreakdown,
    BillCalculateRequest,
)

router = APIRouter()

MAX_PHOTO_BYTES = MAX_UPLOAD_BYTES  # 10 MB; ratelimit.upload_guard refuses larger ones earlier
MAX_FRAME_BYTES = 2 * 1024 * 1024
# A photo sent again within this time gets the answer for the reading it was already used for.
REPEAT_WINDOW = timedelta(hours=1)


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


def _reading_request(body: ConfirmReadingRequest, db: Session, access: Access):
    """What /check-reading and /confirm-reading both start from: the caller's meter, the typed
    value in m3, and (households only) where the photo was taken."""
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
    return meter, submitted, evidence


@router.post("/check-reading", response_model=ReadingCheckResponse)
async def check_reading(
    body: ConfirmReadingRequest,
    db: Session = Depends(get_db),
    access: Access = Depends(household_access),
):
    """What sending this reading would lead to, with nothing stored: the same checks as
    /confirm-reading (anomaly.service.evaluate_reading), which runs them all again on sending."""
    meter, submitted, evidence = _reading_request(body, db, access)
    try:
        result = evaluate_reading(db, meter, submitted, datetime.utcnow(), evidence=evidence,
                                  household=access.staff is None, photo=claim(db, body.photo_id, access.owner))
        if result.refusal is not None:
            block = result.refusal.block
            return ReadingCheckResponse(
                refused=block.reason if block else "duplicate",
                opens_on=block.opens_on if block else None,
                previous_reading_m3=meter.last_reading,
            )
        reason = review_reason(result)
        return ReadingCheckResponse(
            needs_review=reason is not None, reason=reason,
            previous_reading_m3=meter.last_reading, consumption_m3=round(result.consumption_m3, 3),
        )
    finally:
        db.rollback()  # evaluate_reading writes nothing; this makes sure the session holds nothing either


def _already_sent(db: Session, photo_id: Optional[str], owner: str) -> Optional[ConfirmReadingResponse]:
    """The same photo sent again (a retry after a lost answer): the reading it was used for, if
    that was within the last hour and not rejected. Otherwise None."""
    if not photo_id:
        return None
    photo = db.get(PhotoRead, photo_id)
    if photo is None or photo.owner != owner or photo.reading_id is None:
        return None
    reading = db.get(Reading, photo.reading_id)
    if reading is None or datetime.utcnow() - reading.submission_time > REPEAT_WINDOW:
        return None
    if reading.validation_status == READING_REJECTED:
        raise HTTPException(status_code=409, detail="This photo was already used for a reading. Take a new photo.")
    flag = (db.query(AnomalyFlag).filter(AnomalyFlag.reading_id == reading.reading_id)
            .order_by(AnomalyFlag.id.desc()).first())
    bill = db.query(Bill).filter(Bill.reading_id == reading.reading_id).first()
    kind = AnomalyType(flag.anomaly_type) if flag else AnomalyType.NORMAL
    anomaly = AnomalyResultSchema(
        household_id=reading.meter_id, reading_m3=reading.submitted_value, anomaly_score=reading.anomaly_score,
        is_anomaly=flag is not None, anomaly_type=kind.value, needs_retake=False,
        message_for_household=flag.message_for_household if flag else message_for(kind),
        features=(flag.features or {}) if flag else {}, flag_id=flag.id if flag else None,
        pending_review=reading.validation_status == READING_PENDING,
    )
    return ConfirmReadingResponse(
        success=True, repeated=True, consumption_m3=reading.implied_consumption,
        validation_status=reading.validation_status, anomaly_flagged=flag is not None,
        anomaly_score=reading.anomaly_score, anomaly=anomaly,
        bill_id=bill.bill_id if bill else None, bill_amount=bill.amount_due if bill else None,
    )


@router.post("/confirm-reading", response_model=ConfirmReadingResponse)
async def confirm_reading(
    body: ConfirmReadingRequest,
    request: Request,
    db: Session = Depends(get_db),
    access: Access = Depends(household_access),
):
    """A household confirms its reading (or staff enter one). A household's photo location is
    checked against the meter's (app/anomaly/location.py); staff readings are not. Sending the
    same photo again returns the reading it was already used for (repeated: true)."""
    meter, submitted, evidence = _reading_request(body, db, access)
    repeat = _already_sent(db, body.photo_id, access.owner)
    if repeat is not None:
        return repeat
    photo = claim(db, body.photo_id, access.owner)
    try:
        sub = submit_reading(db, meter, body.customer_id, submitted, method="camera", evidence=evidence,
                             household=access.staff is None, photo=photo)
    except ReadingRefused as refused:
        # 409: the app shows its own words for a block's reason (see GET /customers/{id}).
        raise HTTPException(status_code=409, detail=refused.message)
    if access.staff is not None:
        record(db, access.staff.username, "reading_entered", target=meter.meter_id,
               detail=f"{submitted:.3f} m3, {sub.reading.validation_status}", request=request)
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
    rates = [rate for _, rate in billing.tariff()["tiers"]]
    return {
        "consumption_m3": body.consumption_m3,
        "breakdown": {
            f"tier{n}": {"units": data[f"tier{n}_units"], "rate_rwf": rates[n - 1], "amount": data[f"tier{n}_amount"]}
            for n in range(1, 5)
        },
        "service_charge": data["service_charge"],
        "total_amount_due": data["total"],
        "currency": "RWF",
    }
