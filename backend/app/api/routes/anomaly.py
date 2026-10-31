from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from app.models import AnomalyFlag, FLAG_STATUS_OPEN, FLAG_STATUS_RESOLVED, MessageDismissal
from app.anomaly.config import AnomalyConfig
from app.anomaly.edits import changed_positions, household_digits
from app.anomaly.review import ReviewError, resolve_flag
from app.anomaly.service import notify_household, score_submission
from app.services.audit import record
from app.services.balance import current_consumption
from app.services.photo_evidence import photo_for_reading
from app.models import StaffUser
from app.api.deps import Access, household_access
from app.api.deps import require_staff, staff_from_header
from app.db.session import get_db
from app.anomaly.statuses import NOT_CONFIRMED, READING_PENDING
from app.models import Customer, Meter, Reading
from app.schemas import (
    AnomalyFlagOut,
    AnomalyResultSchema,
    AnomalyScoreRequest,
    HistoryPoint,
    ResolveFlagRequest,
    ResolveFlagResponse,
    ReviewItem,
)

router = APIRouter(prefix="/api/anomaly")
CONFIG = AnomalyConfig()  # only the meter's digit layout (8 wheels, 3 for litres) is used here


def _history_point(r: Reading, corrected: dict) -> HistoryPoint:
    used = corrected.get(r.reading_id, r.implied_consumption)
    return HistoryPoint(
        date=r.submission_time, reading_m3=r.effective_value, consumption_m3=used,
        original_reading_m3=r.submitted_value if r.effective_value != r.submitted_value else None,
        original_consumption_m3=r.implied_consumption if used != r.implied_consumption else None,
    )


def _previous_reading(flag: AnomalyFlag, reading: Optional[Reading], meter: Optional[Meter]) -> Optional[float]:
    """A held reading is measured from the meter's last accepted reading (what _accept bills from).
    An already-billed one moved the meter on, so its flag's own record of the previous reading is used."""
    if reading is not None and reading.validation_status == READING_PENDING and meter is not None:
        return meter.last_reading
    return (flag.features or {}).get("previous_reading_m3")


@router.post("/score", response_model=AnomalyResultSchema)
async def score(
    body: AnomalyScoreRequest, db: Session = Depends(get_db), _staff: StaffUser = Depends(require_staff)
):
    try:
        result = score_submission(
            db, body.household_id, body.reading_digits, body.reading_date or datetime.utcnow()
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    db.commit()
    return AnomalyResultSchema(**result.to_dict(), actions=notify_household(db, result))


@router.get("/flags", response_model=List[AnomalyFlagOut])
async def list_flags(
    household_id: Optional[str] = None,
    status: Optional[str] = Query(None, pattern=f"^({FLAG_STATUS_OPEN}|{FLAG_STATUS_RESOLVED})$"),
    requires_staff_review: Optional[bool] = None,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    # A household reads its own flags (without the messages it deleted); listing every
    # household's is staff only.
    access = None
    if household_id:
        access = household_access(authorization, db)
        access.require_meter(household_id)
    else:
        staff_from_header(authorization, db)
    query = db.query(AnomalyFlag)
    if household_id:
        query = query.filter(AnomalyFlag.household_id == household_id)
    if access is not None and access.staff is None:
        query = query.filter(~AnomalyFlag.id.in_(db.query(MessageDismissal.flag_id)))
    if status:
        query = query.filter(AnomalyFlag.status == status)
    if requires_staff_review is not None:
        query = query.filter(AnomalyFlag.requires_staff_review == requires_staff_review)
    flags = query.order_by(AnomalyFlag.created_at.desc()).all()
    reading_ids = [f.reading_id for f in flags if f.reading_id is not None]
    statuses = dict(
        db.query(Reading.reading_id, Reading.validation_status).filter(Reading.reading_id.in_(reading_ids)).all()
    ) if reading_ids else {}
    return [
        AnomalyFlagOut.model_validate(f).model_copy(update={"reading_status": statuses.get(f.reading_id)})
        for f in flags
    ]


@router.delete("/flags/{flag_id}/message", status_code=204)
async def delete_message(flag_id: int, db: Session = Depends(get_db), access: Access = Depends(household_access)):
    """A household deletes a message from its Messages list (the flag stays for staff). A message
    about a reading still being checked cannot be deleted: its outcome is still to come."""
    flag = db.get(AnomalyFlag, flag_id)
    if not flag or access.staff is not None or not access.owns_meter(flag.household_id):
        raise HTTPException(status_code=404, detail="Message not found")
    reading = db.get(Reading, flag.reading_id) if flag.reading_id else None
    if flag.status == FLAG_STATUS_OPEN and reading is not None and reading.validation_status == "pending_review":
        raise HTTPException(status_code=409, detail="This reading is still being checked.")
    if not db.get(MessageDismissal, flag_id):
        db.add(MessageDismissal(flag_id=flag_id))
        db.commit()


@router.patch("/flags/{flag_id}/resolve", response_model=ResolveFlagResponse)
async def resolve(
    flag_id: int,
    request: Request,
    body: Optional[ResolveFlagRequest] = None,
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(require_staff),
):
    """Close a flag. For a pending reading send {"outcome": "accept"} or {"outcome": "reject"}."""
    flag = db.query(AnomalyFlag).filter(AnomalyFlag.id == flag_id).first()
    if not flag:
        raise HTTPException(status_code=404, detail="Anomaly flag not found")
    reason = (body.reason or "").strip() if body else ""
    if body and body.outcome == "reject" and len(reason) < 3:
        raise HTTPException(status_code=422, detail="Say why the reading is rejected.")
    try:
        result = resolve_flag(db, flag, body.outcome if body else None, body.reason_code if body else None)
    except ReviewError as e:
        db.rollback()
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    detail = f"{flag.household_id} {flag.anomaly_type}"
    if result.bill:
        reason = f"bill {result.bill.bill_id}, RWF {result.bill.amount_due:,.0f}" + (f", {reason}" if reason else "")
    elif result.outcome == "accept":
        reason = "starting point, no bill" + (f", {reason}" if reason else "")
    record(db, staff.username, result.outcome or "close", target=f"flag {flag.id}",
           detail=f"{detail}: {reason}" if reason else detail, request=request)
    db.refresh(flag)
    return ResolveFlagResponse(
        **AnomalyFlagOut.model_validate(flag).model_dump(exclude={"reading_status"}),
        outcome=result.outcome,
        reading_status=result.reading_status,
        bill_id=result.bill.bill_id if result.bill else None,
        amount_due=result.bill.amount_due if result.bill else None,
        actions=result.actions,
    )


@router.get("/review-queue", response_model=List[ReviewItem])
async def review_queue(db: Session = Depends(get_db), _staff: StaffUser = Depends(require_staff)):
    """Open flags that need a staff decision, oldest first, each with the
    reading, the household and its recent use, so a decision needs no
    second screen. Staff only."""
    flags = (
        db.query(AnomalyFlag)
        .filter(AnomalyFlag.status == FLAG_STATUS_OPEN, AnomalyFlag.requires_staff_review.is_(True))
        .order_by(AnomalyFlag.created_at.asc())
        .all()
    )
    items = []
    for flag in flags:
        reading = db.query(Reading).filter(Reading.reading_id == flag.reading_id).first() if flag.reading_id else None
        customer = db.query(Customer).filter(Customer.meter_id == flag.household_id).first()
        meter = db.get(Meter, flag.household_id)
        history_query = db.query(Reading).filter(
            Reading.meter_id == flag.household_id, Reading.validation_status.notin_(NOT_CONFIRMED),
        )
        if reading:
            history_query = history_query.filter(Reading.submission_time < reading.submission_time)
        history = (
            history_query
            .order_by(Reading.submission_time.desc())
            .limit(6)
            .all()
        )
        photo = photo_for_reading(db, reading.reading_id) if reading else None
        corrected = current_consumption(db, [r.reading_id for r in history])
        items.append(ReviewItem(
            # reading_status tells the two kinds apart: pending_review needs accept or reject;
            # an already-billed reading (valid, anomaly_flagged) only needs closing after follow-up.
            flag=AnomalyFlagOut.model_validate(flag).model_copy(
                update={"reading_status": reading.validation_status if reading else None}
            ),
            reading_m3=reading.submitted_value if reading else None,
            consumption_m3=reading.implied_consumption if reading else None,
            previous_reading_m3=_previous_reading(flag, reading, meter),
            submitted_at=reading.submission_time if reading else None,
            reading_confidence=reading.crnn_confidence if reading else None,
            customer_id=customer.customer_id if customer else None,
            customer_name=customer.name if customer else None,
            sector=customer.sector if customer else None,
            meter_serial=meter.serial_number if meter else None,
            reading_id=reading.reading_id if reading else None,
            photo_available=bool(photo and photo.image_jpeg),
            reader_digits=photo.reader_digits if photo else None,
            household_digits=household_digits(reading.submitted_value, CONFIG) if reading else None,
            changed_positions=(changed_positions(photo.reader_digits, household_digits(reading.submitted_value, CONFIG))
                               if photo and reading else []),
            edited_by_household=photo.edited if photo else None,
            reader_models=photo.models if photo else None,
            history=[
                _history_point(r, corrected)
                for r in reversed(history)
            ],
        ))
    return items


@router.get("/readings/{reading_id}/photo", responses={200: {"content": {"image/jpeg": {}}}})
async def reading_photo(reading_id: int, db: Session = Depends(get_db), _staff: StaffUser = Depends(require_staff)):
    """The photo a reading came from, for the officer checking it. Staff only; never cached."""
    photo = photo_for_reading(db, reading_id)
    if not photo or not photo.image_jpeg:
        raise HTTPException(status_code=404, detail="No photo kept for this reading")
    return Response(photo.image_jpeg, media_type="image/jpeg", headers={"Cache-Control": "private, no-store"})
