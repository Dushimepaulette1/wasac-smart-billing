from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from anomaly.db_models import FLAG_STATUS_OPEN, FLAG_STATUS_RESOLVED, AnomalyFlag
from anomaly.review import ReviewError, resolve_flag
from anomaly.service import notify_household, score_submission
from database import get_db
from schemas import (
    AnomalyFlagOut,
    AnomalyResultSchema,
    AnomalyScoreRequest,
    ResolveFlagRequest,
    ResolveFlagResponse,
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
    db: Session = Depends(get_db),
):
    query = db.query(AnomalyFlag)
    if household_id:
        query = query.filter(AnomalyFlag.household_id == household_id)
    if status:
        query = query.filter(AnomalyFlag.status == status)
    if requires_staff_review is not None:
        query = query.filter(AnomalyFlag.requires_staff_review == requires_staff_review)
    return query.order_by(AnomalyFlag.created_at.desc()).all()


@router.patch("/flags/{flag_id}/resolve", response_model=ResolveFlagResponse)
async def resolve(flag_id: int, body: Optional[ResolveFlagRequest] = None, db: Session = Depends(get_db)):
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
