"""Asking for a meter's starting reading to change, and a second person's decision on it.

A new starting reading decides what the next bill measures: raising it hides water that was used,
and lowering it charges for water that was not. So a change waits for a different supervisor or
admin. The one exception is a meter with no starting value yet, where nothing can be hidden: it
applies at once. If the record changes while a request waits, the request goes STALE.
"""
from datetime import datetime
from typing import Optional

from fastapi import Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.anomaly.evaluation import has_baseline
from app.anomaly.service import lock_meter
from app.models import Meter
from app.models.meter_correction import APPLIED, AWAITING, DECLINED, STALE, MeterCorrection
from app.services.audit import record
from app.services.meter_correction import CorrectionError, correct_meter, reading_in_review


def _apply(db: Session, row: MeterCorrection, meter: Meter, staff: str, request: Optional[Request]) -> None:
    old = meter.last_reading
    correct_meter(db, meter, row.reading_m3)
    row.status, row.decided_by, row.decided_at = APPLIED, staff, datetime.utcnow()
    asked = "" if row.requested_by == staff else f" (asked for by {row.requested_by})"
    record(db, staff, "meter_corrected", target=meter.meter_id,
           detail=f"{old:.3f} -> {meter.last_reading:.3f} m3: {row.reason}{asked}"[:300], request=request, commit=False)


def request_correction(db: Session, meter: Meter, customer_id: str, reading_m3: float, reason: str, staff: str,
                       request: Optional[Request] = None) -> MeterCorrection:
    """Record the request, or apply it at once for a meter with no starting value. Commits."""
    lock_meter(db, meter.meter_id)
    if reading_in_review(db, meter):
        db.rollback()
        raise CorrectionError(409, "A reading from this household is waiting in the review queue: decide on it first.")
    row = MeterCorrection(meter_id=meter.meter_id, customer_id=customer_id, current_m3=meter.last_reading,
                          reading_m3=round(reading_m3, 3), reason=reason, requested_by=staff)
    db.add(row)
    if has_baseline(db, meter):
        record(db, staff, "meter_correction_requested", target=meter.meter_id,
               detail=f"{meter.last_reading:.3f} -> {row.reading_m3:.3f} m3: {reason}"[:300], request=request, commit=False)
    else:
        _apply(db, row, meter, staff, request)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise CorrectionError(409, "A correction for this meter is already waiting for approval.")
    return row


def _open_request(db: Session, correction_id: int, staff: str) -> MeterCorrection:
    row = db.get(MeterCorrection, correction_id)
    if row is None:
        raise CorrectionError(404, "Correction not found")
    lock_meter(db, row.meter_id)
    db.refresh(row)
    if row.status != AWAITING:
        db.rollback()
        raise CorrectionError(409, "This correction has already been decided.")
    if row.requested_by == staff:
        db.rollback()
        raise CorrectionError(403, "A different supervisor or admin must decide this.")
    return row


def approve_correction(db: Session, correction_id: int, staff: str, request: Optional[Request] = None) -> MeterCorrection:
    """A different supervisor or admin approves. The record must not have changed. Commits."""
    row = _open_request(db, correction_id, staff)
    meter = db.get(Meter, row.meter_id)
    if meter.last_reading != row.current_m3:
        row.status, row.decided_by, row.decided_at = STALE, staff, datetime.utcnow()
        row.decision_reason = "The meter's record changed before approval"
        record(db, staff, "meter_correction_stale", target=meter.meter_id, request=request, commit=False)
        db.commit()
        raise CorrectionError(409, "The meter's record changed since this was asked for. Ask again.")
    try:
        _apply(db, row, meter, staff, request)
    except CorrectionError:
        db.rollback()
        raise
    db.commit()
    return row


def decline_correction(db: Session, correction_id: int, staff: str, reason: str,
                       request: Optional[Request] = None) -> MeterCorrection:
    row = _open_request(db, correction_id, staff)
    row.status, row.decided_by, row.decided_at, row.decision_reason = DECLINED, staff, datetime.utcnow(), reason
    record(db, staff, "meter_correction_declined", target=row.meter_id, detail=reason[:300], request=request, commit=False)
    db.commit()
    return row
