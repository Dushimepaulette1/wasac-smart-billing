from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from anomaly.db_models import FLAG_STATUS_OPEN, FLAG_STATUS_RESOLVED, AnomalyFlag
from anomaly.service import notify_household, score_submission
from database import get_db
from schemas import AnomalyFlagOut, AnomalyResultSchema, AnomalyScoreRequest

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


@router.patch("/flags/{flag_id}/resolve", response_model=AnomalyFlagOut)
async def resolve_flag(flag_id: int, db: Session = Depends(get_db)):
    flag = db.query(AnomalyFlag).filter(AnomalyFlag.id == flag_id).first()
    if not flag:
        raise HTTPException(status_code=404, detail="Anomaly flag not found")
    if flag.status != FLAG_STATUS_RESOLVED:
        flag.status = FLAG_STATUS_RESOLVED
        flag.resolved_at = datetime.utcnow()
        db.commit()
        db.refresh(flag)
    return flag
