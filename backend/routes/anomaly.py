from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from anomaly.db_models import FLAG_STATUS_OPEN, FLAG_STATUS_RESOLVED, AnomalyFlag
from anomaly.review import ReviewError, resolve_flag
from anomaly.service import notify_household, score_submission
from auth.models import StaffUser
from auth.routes import require_staff
from database import Customer, Reading, get_db
from schemas import (
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
async def score(body: AnomalyScoreRequest, db: Session = Depends(get_db)):
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
    if not household_id:
        require_staff(authorization, db)
    query = db.query(AnomalyFlag)
    if household_id:
        query = query.filter(AnomalyFlag.household_id == household_id)
    if status:
        query = query.filter(AnomalyFlag.status == status)
    if requires_staff_review is not None:
        query = query.filter(AnomalyFlag.requires_staff_review == requires_staff_review)
    return query.order_by(AnomalyFlag.created_at.desc()).all()


@router.patch("/flags/{flag_id}/resolve", response_model=ResolveFlagResponse)
async def resolve(
    flag_id: int,
    body: Optional[ResolveFlagRequest] = None,
    db: Session = Depends(get_db),
    _staff: StaffUser = Depends(require_staff),
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
    db.refresh(flag)
    return ResolveFlagResponse(
        **AnomalyFlagOut.model_validate(flag).model_dump(),
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
        items.append(ReviewItem(
            flag=AnomalyFlagOut.model_validate(flag),
            reading_m3=reading.submitted_value if reading else None,
            submitted_at=reading.submission_time if reading else None,
            reading_confidence=reading.crnn_confidence if reading else None,
            customer_id=customer.customer_id if customer else None,
            customer_name=customer.name if customer else None,
            sector=customer.sector if customer else None,
            history=[
                HistoryPoint(date=r.submission_time, reading_m3=r.submitted_value, consumption_m3=r.implied_consumption)
                for r in reversed(history)
            ],
        ))
    return items
