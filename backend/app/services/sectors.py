"""The staff sector view: households grouped by Kigali sector, the sectors that need attention first.

A sector needs attention when it has readings held for an officer or households that may have a
leak (the leak alert in app/services/usage.py, or an open high-use flag). What is owed comes from
app/services/balance.py, the only definition of it.

Balances, flags and confirmed histories are fetched in bulk. History calculations still run in
memory; a utility-wide service needs pagination and bounded history windows.
"""
from datetime import datetime, timedelta
from statistics import median
from typing import Dict, List

from sqlalchemy.orm import Session

from app.anomaly.rules import AnomalyType
from app.anomaly.features import ReadingPoint
from app.anomaly.statuses import NOT_CONFIRMED, READING_PENDING
from app.models import FLAG_STATUS_OPEN, AnomalyFlag, Customer, Meter, Reading
from app.schemas import SectorHousehold, SectorSummaryOut
from app.services.balance import balances_for_customers
from app.services.usage import usage_summary

HIGH_USE_TYPES = (AnomalyType.SPIKE.value, AnomalyType.SUSTAINED_HIGH.value)
MONTH_DAYS = 30


def sector_summaries(db: Session) -> List[SectorSummaryOut]:
    now = datetime.utcnow()
    high_use = {
        meter_id for (meter_id,) in db.query(AnomalyFlag.household_id)
        .filter(AnomalyFlag.status == FLAG_STATUS_OPEN, AnomalyFlag.anomaly_type.in_(HIGH_USE_TYPES))
    }
    meters: Dict[str, Meter] = {m.meter_id: m for m in db.query(Meter).all()}
    customers = db.query(Customer).order_by(Customer.name).all()
    account_balances = balances_for_customers(db, [c.customer_id for c in customers])
    pending = {m for (m,) in db.query(Reading.meter_id).filter(Reading.validation_status == READING_PENDING).distinct()}
    histories: Dict[str, List[ReadingPoint]] = {}
    newest_ids: Dict[str, int] = {}
    for r in (db.query(Reading).filter(Reading.validation_status.notin_(NOT_CONFIRMED),
                                     Reading.submission_time < now + timedelta(seconds=1))
              .order_by(Reading.submission_time, Reading.reading_id)):
        value = r.corrected_value_m3 if r.corrected_value_m3 is not None else r.submitted_value
        histories.setdefault(r.meter_id, []).append(ReadingPoint(date=r.submission_time, reading_m3=value))
        newest_ids[r.meter_id] = r.reading_id
    groups: Dict[str, List[SectorHousehold]] = {}
    usual: Dict[str, List[float]] = {}
    for c in customers:
        sector = (c.sector or "").strip()
        meter = meters.get(c.meter_id)
        held = possible_leak = False
        if meter is not None:
            held = meter.meter_id in pending
            summary = usage_summary(db, meter, now, history=histories.get(meter.meter_id, []),
                                    newest_reading_id=newest_ids.get(meter.meter_id))
            possible_leak = summary.leak_warning or meter.meter_id in high_use
            if summary.usual_daily_m3 is not None:
                usual.setdefault(sector, []).append(summary.usual_daily_m3 * MONTH_DAYS)
        owed = round(sum(b.outstanding for b in account_balances.get(c.customer_id, {}).values() if not b.settled), 2)
        groups.setdefault(sector, []).append(SectorHousehold(
            customer_id=c.customer_id, name=c.name, meter_id=c.meter_id or "", held=held,
            possible_leak=possible_leak, owed=owed,
        ))

    out = []
    for sector, households in groups.items():
        values = usual.get(sector)
        out.append(SectorSummaryOut(
            sector=sector,
            households=len(households),
            held_readings=sum(h.held for h in households),
            possible_leaks=sum(h.possible_leak for h in households),
            usual_monthly_m3=round(median(values), 1) if values else None,
            owed=round(sum(h.owed for h in households), 2),
            attention=[h for h in households if h.held or h.possible_leak],
        ))
    # Readings to check and possible leaks first, then money owed, then by name.
    out.sort(key=lambda s: (-(s.held_readings + s.possible_leaks), -s.owed, s.sector))
    return out
