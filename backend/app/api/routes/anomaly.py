from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from app.models import AnomalyFlag, FLAG_STATUS_OPEN, FLAG_STATUS_RESOLVED
from app.anomaly.review import ReviewError, resolve_flag
from app.anomaly.service import notify_household, score_submission
from app.services.audit import record
from app.services.photo_evidence import photo_for_reading
from app.models import StaffUser
from app.api.deps import household_access
from app.api.deps import require_staff, staff_from_header
from app.db.session import get_db
from app.models import Customer, Reading
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
    # A household reads its own flags; listing every household's is staff only.
    if household_id:
        household_access(authorization, db).require_meter(household_id)
    else:
        staff_from_header(authorization, db)
    query = db.query(AnomalyFlag)
    if household_id:
        query = query.filter(AnomalyFlag.household_id == household_id)
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
    try:
        result = resolve_flag(db, flag, body.outcome if body else None)
    except ReviewError as e:
        db.rollback()
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    record(db, staff.username, result.outcome or "close", target=f"flag {flag.id}",
           detail=f"{flag.household_id} {flag.anomaly_type}", request=request)
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
        history = (
            db.query(Reading)
            .filter(Reading.meter_id == flag.household_id, Reading.validation_status == "valid")
            .order_by(Reading.submission_time.desc())
            .limit(6)
            .all()
        )
        photo = photo_for_reading(db, reading.reading_id) if reading else None
        items.append(ReviewItem(
            # reading_status tells the two kinds apart: pending_review needs accept or reject;
            # an already-billed reading (valid, anomaly_flagged) only needs closing after follow-up.
            flag=AnomalyFlagOut.model_validate(flag).model_copy(
                update={"reading_status": reading.validation_status if reading else None}
            ),
            reading_m3=reading.submitted_value if reading else None,
            submitted_at=reading.submission_time if reading else None,
            reading_confidence=reading.crnn_confidence if reading else None,
            customer_id=customer.customer_id if customer else None,
            customer_name=customer.name if customer else None,
            sector=customer.sector if customer else None,
            reading_id=reading.reading_id if reading else None,
            photo_available=bool(photo and photo.image_jpeg),
            reader_digits=photo.reader_digits if photo else None,
            edited_by_household=photo.edited if photo else None,
            reader_models=photo.models if photo else None,
            history=[
                HistoryPoint(date=r.submission_time, reading_m3=r.submitted_value, consumption_m3=r.implied_consumption)
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
