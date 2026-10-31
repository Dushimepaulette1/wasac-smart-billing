"""Correcting a reading that was already billed. Nothing billed or paid is overwritten.

A reading's bill measures reading - start, so changing a reading changes that bill and the next
bill, which starts from it. Both are recalculated with their own tariff version and each gets a
BillAdjustment, in one correction. readings.corrected_value_m3 holds the new value (submitted_value
stays); meters.last_reading moves only if this is the latest reading, so later periods stay right.

A first bill measured from nothing (a meter added with no starting value, so the whole register was
charged) is a BASELINE correction: a supervisor gives the true starting reading, and the bill is
recalculated from it. If that equals the reading, the reading was only ever the starting point and
nothing is owed for it: the bill's charges become zero, as for a first reading today. The reading
itself can be corrected at the same time, which also recalculates the next bill.

A correction that only lowers charges applies at once. One that charges more on any bill waits for
a different supervisor or admin, and is recalculated then: if the bills changed meanwhile it goes
STALE and a new one is needed. Refused while a reading is waiting for review or a payment on an
affected bill is open (either could change the figures underneath it).
"""
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from fastapi import Request
from sqlalchemy.orm import Session

from app.anomaly.service import lock_meter
from app.anomaly.statuses import NOT_CONFIRMED, READING_PENDING
from app.models import Bill, Customer, Meter, Payment, Reading
from app.models.bill_correction import (
    APPLIED, AWAITING, BASELINE, DECLINED, READING, STALE, BillAdjustment, BillCorrection,
)
from app.services.audit import record
from app.services.balance import balances, in_flight, settle
from app.services.billing import bill_tariff, calculate_bill
from app.services.meter_correction import CORRECTION, MAX_READING_M3
from app.services.sms import send_sms


class BillCorrectionError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code, self.detail = status_code, detail


@dataclass
class Change:
    bill: Bill
    consumption_before: float
    consumption_after: float
    amount_before: float
    amount_after: float
    tiers: dict
    tariff_version: str

    @property
    def delta(self) -> float:
        return round(self.amount_after - self.amount_before, 2)


def _current_consumption(db: Session, bill: Bill) -> float:
    latest = (
        db.query(BillAdjustment)
        .join(BillCorrection, BillCorrection.id == BillAdjustment.correction_id)
        .filter(BillAdjustment.bill_id == bill.bill_id, BillCorrection.status == APPLIED)
        .order_by(BillAdjustment.id.desc()).first()
    )
    return latest.consumption_after if latest else bill.consumption_m3


def _change(db: Session, bill: Bill, after: float, charges: float, no_charge: bool = False) -> Change:
    version = bill_tariff(bill)["version"]
    data = calculate_bill(after, version)
    return Change(bill=bill, consumption_before=_current_consumption(db, bill), consumption_after=round(after, 3),
                  amount_before=charges, amount_after=0.0 if no_charge else round(data["total"], 2),
                  tiers=data, tariff_version=version)


def measured_from_zero(db: Session, bill: Bill, reading: Reading) -> bool:
    """Did this bill charge the whole register? No confirmed reading before it, and its volume is the
    reading itself. Read-only; false once a baseline correction has given it a real start."""
    if not reading.effective_value or abs(_current_consumption(db, bill) - reading.effective_value) > 0.0005:
        return False
    return db.query(Reading.reading_id).filter(
        Reading.meter_id == reading.meter_id,
        Reading.submission_time < reading.submission_time,
        Reading.validation_status.notin_(NOT_CONFIRMED),
    ).first() is None


def plan_correction(db: Session, reading: Reading, corrected: float, start_m3: Optional[float] = None) -> List[Change]:
    """What this correction would do to each bill; refuses what cannot be applied safely. Read-only.
    start_m3: a baseline correction, the true starting reading."""
    if not 0 <= corrected <= MAX_READING_M3:
        raise BillCorrectionError(422, "A meter reading is between 0 and 99999.999 m³.")
    if reading.validation_status in NOT_CONFIRMED:
        raise BillCorrectionError(409, "Only an accepted reading can be corrected.")
    bill = db.query(Bill).filter(Bill.reading_id == reading.reading_id).first()
    if bill is None:
        raise BillCorrectionError(409, "This reading has no bill. Use the meter correction instead.")
    same_value = abs(corrected - reading.effective_value) < 0.0005
    if same_value and start_m3 is None:
        raise BillCorrectionError(409, "This reading already has that value.")
    if start_m3 is not None:
        if not measured_from_zero(db, bill, reading):
            raise BillCorrectionError(409, "Only a first bill charged from no starting reading can be given a baseline.")
        if not 0 <= start_m3 <= MAX_READING_M3:
            raise BillCorrectionError(422, "A meter reading is between 0 and 99999.999 m³.")
    if db.query(Reading.reading_id).filter(Reading.meter_id == reading.meter_id,
                                           Reading.validation_status == READING_PENDING).first():
        raise BillCorrectionError(409, "A reading from this household is waiting in the review queue: decide on it first.")
    if db.query(BillCorrection.id).filter(BillCorrection.reading_id == reading.reading_id,
                                          BillCorrection.status == AWAITING).first():
        raise BillCorrectionError(409, "A correction of this reading is already waiting for approval.")

    start = start_m3 if start_m3 is not None else round(reading.effective_value - _current_consumption(db, bill), 3)
    if corrected < start:
        raise BillCorrectionError(409, f"The reading before this one is {start:.3f} m³, so this bill would be negative. "
                                       "Correct that reading first, or record a meter replacement.")
    money = balances(db, bill.customer_id)
    starting_point = start_m3 is not None and corrected - start < 0.0005
    changes = [_change(db, bill, corrected - start, money[bill.bill_id].charges, no_charge=starting_point)]

    following = (
        db.query(Reading)
        .filter(Reading.meter_id == reading.meter_id, Reading.submission_time > reading.submission_time,
                Reading.validation_status.notin_(NOT_CONFIRMED))
        .order_by(Reading.submission_time).first()
    )
    # After a staff meter correction the count starts again: nothing later depends on this reading.
    if following is not None and following.submission_method != CORRECTION and not same_value:
        next_bill = db.query(Bill).filter(Bill.reading_id == following.reading_id).first()
        if corrected > following.effective_value:
            raise BillCorrectionError(409, f"The next reading is {following.effective_value:.3f} m³, so the next bill "
                                           "would be negative. Correct that reading first.")
        if next_bill is not None:
            changes.append(_change(db, next_bill, following.effective_value - corrected, money[next_bill.bill_id].charges))

    open_payment = db.query(Payment.id).filter(Payment.bill_id.in_([c.bill.bill_id for c in changes]),
                                               in_flight()).first()
    if open_payment:
        raise BillCorrectionError(409, "A payment on this bill is still open. Wait for it to finish, then correct it.")
    return changes


def needs_approval(changes: List[Change]) -> bool:
    return any(c.delta > 0 for c in changes)


def _apply(db: Session, correction: BillCorrection, reading: Reading, actor: str, request: Optional[Request]) -> None:
    correction.status = APPLIED
    if abs(correction.corrected_value_m3 - reading.effective_value) >= 0.0005:  # a baseline may leave it as it is
        reading.corrected_value_m3 = correction.corrected_value_m3
        meter = db.get(Meter, reading.meter_id)
        later = db.query(Reading.reading_id).filter(
            Reading.meter_id == reading.meter_id, Reading.submission_time > reading.submission_time,
            Reading.validation_status.notin_(NOT_CONFIRMED)).first()
        if later is None:
            meter.last_reading = correction.corrected_value_m3
    db.flush()
    settle(db, correction.customer_id, actor, request)


def request_correction(
    db: Session, reading: Reading, corrected: float, reason: str, staff: str, request_key: Optional[str],
    request: Optional[Request] = None, start_m3: Optional[float] = None,
) -> BillCorrection:
    """Record a correction: applied, or waiting for approval if it charges more. Commits. The same
    request_key returns the first correction, so a repeated request cannot adjust twice."""
    key = (request_key or uuid.uuid4().hex)[:64]
    lock_meter(db, reading.meter_id)
    existing = db.query(BillCorrection).filter(BillCorrection.request_key == key).first()
    if existing:
        db.rollback()
        return existing
    changes = plan_correction(db, reading, corrected, start_m3)
    bill = changes[0].bill
    correction = BillCorrection(
        customer_id=bill.customer_id, reading_id=reading.reading_id, value_before_m3=reading.effective_value,
        corrected_value_m3=round(corrected, 3), reason=reason[:200], status=AWAITING, requested_by=staff,
        request_key=key, kind=READING if start_m3 is None else BASELINE, start_m3=start_m3,
    )
    db.add(correction)
    db.flush()
    for c in changes:
        db.add(BillAdjustment(
            correction_id=correction.id, bill_id=c.bill.bill_id, consumption_before=c.consumption_before,
            consumption_after=c.consumption_after, amount_before=c.amount_before, amount_after=c.amount_after,
            amount_delta=c.delta, tiers=c.tiers, tariff_version=c.tariff_version,
        ))
    net = sum(c.delta for c in changes)
    record(db, staff, "bill_correction_requested", target=f"correction {correction.id}",
           detail=f"{correction.value_before_m3:.3f} -> {correction.corrected_value_m3:.3f} m3, RWF {net:+,.2f}: {reason}",
           request=request, commit=False)
    if not needs_approval(changes):
        db.flush()
        _apply(db, correction, reading, staff, request)
        record(db, staff, "bill_corrected", target=f"correction {correction.id}",
               detail=f"reading {reading.reading_id}, RWF {net:+,.2f}", request=request, commit=False)
    db.commit()
    if correction.status == APPLIED:
        _tell_household(db, correction)
    return correction


def _pending_correction(db: Session, correction_id: int, staff: str) -> BillCorrection:
    correction = db.get(BillCorrection, correction_id)
    if correction is None:
        raise BillCorrectionError(404, "Correction not found")
    if correction.status != AWAITING:
        raise BillCorrectionError(409, "This correction has already been decided.")
    if correction.requested_by == staff:
        raise BillCorrectionError(403, "Someone else must decide a correction you asked for.")
    return correction


def approve_correction(db: Session, correction_id: int, staff: str, request: Optional[Request] = None) -> BillCorrection:
    """A different supervisor or admin approves. The figures must still hold, or it goes STALE. Commits."""
    first = db.get(BillCorrection, correction_id)
    if first is None:
        raise BillCorrectionError(404, "Correction not found")
    reading = db.get(Reading, first.reading_id)
    lock_meter(db, reading.meter_id)
    correction = db.query(BillCorrection).filter(BillCorrection.id == correction_id).with_for_update().populate_existing().one()
    correction = _pending_correction(db, correction.id, staff)
    stored = db.query(BillAdjustment).filter(BillAdjustment.correction_id == correction.id).all()
    correction.status = STALE  # while planning, so this correction does not block itself
    db.flush()
    try:
        changes = plan_correction(db, reading, correction.corrected_value_m3, correction.start_m3)
        same = ({(a.bill_id, a.amount_before, a.amount_after) for a in stored}
                == {(c.bill.bill_id, c.amount_before, c.amount_after) for c in changes})
    except BillCorrectionError:
        same = False
    if not same:
        correction.decided_by, correction.decided_at = staff, datetime.utcnow()
        correction.decision_reason = "The bills changed before approval"
        record(db, staff, "correction_stale", target=f"correction {correction.id}", request=request, commit=False)
        db.commit()
        raise BillCorrectionError(409, "The bills changed since this was asked for. Ask for the correction again.")
    correction.status = AWAITING
    correction.decided_by, correction.decided_at = staff, datetime.utcnow()
    _apply(db, correction, reading, staff, request)
    record(db, staff, "correction_approved", target=f"correction {correction.id}",
           detail=f"asked for by {correction.requested_by}", request=request, commit=False)
    db.commit()
    _tell_household(db, correction)
    return correction


def decline_correction(db: Session, correction_id: int, staff: str, reason: str,
                       request: Optional[Request] = None) -> BillCorrection:
    correction = _pending_correction(db, correction_id, staff)
    correction.status = DECLINED
    correction.decided_by, correction.decided_at, correction.decision_reason = staff, datetime.utcnow(), reason[:200]
    record(db, staff, "correction_declined", target=f"correction {correction.id}", detail=reason, request=request, commit=False)
    db.commit()
    return correction


def _tell_household(db: Session, correction: BillCorrection) -> None:
    customer = db.get(Customer, correction.customer_id)
    if customer and customer.phone:
        send_sms(customer.phone, "WASAC: a reading on your account was corrected and your bill updated. "
                                 "Open Mubazi to see the new balance.")
