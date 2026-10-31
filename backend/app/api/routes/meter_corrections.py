"""Setting a meter's starting reading (app/services/meter_correction_requests.py). Supervisors and admins.

    POST /customers/{id}/meter-correction          ask for it; applies at once only with no starting value
    GET  /meter-corrections                        corrections, newest first; ?status=awaiting_approval
    POST /meter-corrections/{id}/approve | decline by someone other than who asked
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.db.session import get_db
from app.models import Customer, Meter, MeterCorrection, StaffUser
from app.schemas import MeterCorrectionDecline, MeterCorrectionOut, MeterCorrectionRequest
from app.services.meter_correction import CorrectionError
from app.services.meter_correction_requests import approve_correction, decline_correction, request_correction

router = APIRouter()


def _out(db: Session, row: MeterCorrection) -> MeterCorrectionOut:
    customer = db.get(Customer, row.customer_id)
    return MeterCorrectionOut(
        id=row.id, status=row.status, customer_id=row.customer_id, customer_name=customer.name if customer else None,
        meter_id=row.meter_id, current_m3=row.current_m3, reading_m3=row.reading_m3, reason=row.reason,
        requested_by=row.requested_by, requested_at=row.requested_at, decided_by=row.decided_by,
        decided_at=row.decided_at, decision_reason=row.decision_reason,
    )


@router.post("/customers/{customer_id}/meter-correction", response_model=MeterCorrectionOut)
async def ask(customer_id: str, body: MeterCorrectionRequest, request: Request, db: Session = Depends(get_db),
              staff: StaffUser = Depends(require_role("supervisor"))):
    customer = db.get(Customer, customer_id)
    meter = db.get(Meter, customer.meter_id) if customer and customer.meter_id else None
    if not meter:
        raise HTTPException(status_code=404, detail="Customer not found")
    try:
        row = request_correction(db, meter, customer_id, body.reading_m3, body.reason.strip(), staff.username, request)
    except CorrectionError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    return _out(db, row)


@router.get("/meter-corrections", response_model=List[MeterCorrectionOut])
async def list_corrections(status: Optional[str] = Query(None), db: Session = Depends(get_db),
                           _staff: StaffUser = Depends(require_role("supervisor"))):
    query = db.query(MeterCorrection)
    if status:
        query = query.filter(MeterCorrection.status == status)
    return [_out(db, row) for row in query.order_by(MeterCorrection.id.desc()).limit(200).all()]


@router.post("/meter-corrections/{correction_id}/approve", response_model=MeterCorrectionOut)
async def approve(correction_id: int, request: Request, db: Session = Depends(get_db),
                  staff: StaffUser = Depends(require_role("supervisor"))):
    try:
        return _out(db, approve_correction(db, correction_id, staff.username, request))
    except CorrectionError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.post("/meter-corrections/{correction_id}/decline", response_model=MeterCorrectionOut)
async def decline(correction_id: int, body: MeterCorrectionDecline, request: Request, db: Session = Depends(get_db),
                  staff: StaffUser = Depends(require_role("supervisor"))):
    try:
        return _out(db, decline_correction(db, correction_id, staff.username, body.reason.strip(), request))
    except CorrectionError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
