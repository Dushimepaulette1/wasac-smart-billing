"""Correcting a billed reading (app/services/bill_corrections.py). Supervisors and admins only.

    POST /customers/{id}/readings/{reading_id}/correction   preview (apply false) or record it
    GET  /bill-corrections                                  corrections, waiting ones first
    POST /bill-corrections/{id}/approve | decline           by someone other than who asked
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.db.session import get_db
from app.models import BillAdjustment, BillCorrection, Customer, Reading, StaffUser
from app.models.bill_correction import AWAITING
from app.schemas import AdjustmentOut, BillCorrectionDecline, BillCorrectionOut, BillCorrectionRequest
from app.services.bill_corrections import (
    BillCorrectionError,
    approve_correction,
    decline_correction,
    needs_approval,
    plan_correction,
    request_correction,
)
from app.utils.meter_value import parse_meter_value

router = APIRouter()
supervisor = require_role("supervisor")


def _out(db: Session, c: BillCorrection) -> BillCorrectionOut:
    customer = db.get(Customer, c.customer_id)
    adjustments = db.query(BillAdjustment).filter(BillAdjustment.correction_id == c.id).order_by(BillAdjustment.id).all()
    return BillCorrectionOut(
        id=c.id, status=c.status, customer_id=c.customer_id, customer_name=customer.name if customer else None,
        reading_id=c.reading_id, value_before_m3=c.value_before_m3, corrected_value_m3=c.corrected_value_m3,
        reason=c.reason, requested_by=c.requested_by, decided_by=c.decided_by, decision_reason=c.decision_reason,
        created_at=c.created_at, decided_at=c.decided_at,
        net_delta=round(sum(a.amount_delta for a in adjustments), 2),
        needs_approval=any(a.amount_delta > 0 for a in adjustments),
        adjustments=[AdjustmentOut.model_validate(a) for a in adjustments],
    )


@router.post("/customers/{customer_id}/readings/{reading_id}/correction", response_model=BillCorrectionOut)
async def correct_billed_reading(
    customer_id: str, reading_id: int, body: BillCorrectionRequest, request: Request,
    db: Session = Depends(get_db), staff: StaffUser = Depends(supervisor),
):
    """apply false: the effect on each bill, nothing stored. apply true: recorded, and applied at
    once unless it charges more, when a different supervisor or admin must approve it."""
    customer = db.get(Customer, customer_id)
    reading = db.get(Reading, reading_id)
    if not customer or not reading or reading.meter_id != customer.meter_id:
        raise HTTPException(status_code=404, detail="Reading not found")
    corrected = parse_meter_value(body.corrected_reading)
    if corrected is None:
        raise HTTPException(status_code=422, detail="Reading must be a number like 00565.846")
    try:
        if body.apply:
            return _out(db, request_correction(db, reading, corrected, body.reason.strip(), staff.username,
                                               body.request_key, request))
        changes = plan_correction(db, reading, corrected)
    except BillCorrectionError as e:
        db.rollback()
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    db.rollback()
    return BillCorrectionOut(
        status="preview", customer_id=customer_id, customer_name=customer.name, reading_id=reading_id,
        value_before_m3=reading.effective_value, corrected_value_m3=corrected, reason=body.reason.strip(),
        requested_by=staff.username, needs_approval=needs_approval(changes),
        net_delta=round(sum(c.delta for c in changes), 2),
        adjustments=[AdjustmentOut(bill_id=c.bill.bill_id, consumption_before=c.consumption_before,
                                   consumption_after=c.consumption_after, amount_before=c.amount_before,
                                   amount_after=c.amount_after, amount_delta=c.delta, tariff_version=c.tariff_version)
                     for c in changes],
    )


@router.get("/bill-corrections", response_model=List[BillCorrectionOut])
async def list_corrections(
    status: Optional[str] = Query(None, max_length=20), db: Session = Depends(get_db),
    _staff: StaffUser = Depends(supervisor),
):
    query = db.query(BillCorrection)
    if status:
        query = query.filter(BillCorrection.status == status)
    rows = query.order_by(BillCorrection.id.desc()).limit(100).all()
    return [_out(db, c) for c in sorted(rows, key=lambda c: c.status != AWAITING)]


@router.post("/bill-corrections/{correction_id}/approve", response_model=BillCorrectionOut)
async def approve(correction_id: int, request: Request, db: Session = Depends(get_db),
                  staff: StaffUser = Depends(supervisor)):
    try:
        return _out(db, approve_correction(db, correction_id, staff.username, request))
    except BillCorrectionError as e:
        db.rollback()
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.post("/bill-corrections/{correction_id}/decline", response_model=BillCorrectionOut)
async def decline(correction_id: int, body: BillCorrectionDecline, request: Request, db: Session = Depends(get_db),
                  staff: StaffUser = Depends(supervisor)):
    try:
        return _out(db, decline_correction(db, correction_id, staff.username, body.reason.strip(), request))
    except BillCorrectionError as e:
        db.rollback()
        raise HTTPException(status_code=e.status_code, detail=e.detail)
