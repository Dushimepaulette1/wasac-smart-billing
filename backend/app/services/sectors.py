"""The staff sector view: households grouped by Kigali sector, the sectors that need attention first.

A sector needs attention when it has readings held for an officer or households that may have a
leak (the leak alert in app/services/usage.py, or an open high-use flag). What is owed comes from
app/services/balance.py, the only definition of it.

It works household by household, which is fine for a pilot's few hundred households; a utility-wide
version would aggregate in SQL.
"""
from datetime import datetime
from statistics import median
from typing import Dict, List

from sqlalchemy.orm import Session

from app.anomaly.rules import AnomalyType
from app.models import FLAG_STATUS_OPEN, AnomalyFlag, Customer, Meter
from app.schemas import SectorHousehold, SectorSummaryOut
from app.services.balance import balances
from app.services.reading_window import PENDING, reading_block
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
    groups: Dict[str, List[SectorHousehold]] = {}
    usual: Dict[str, List[float]] = {}
    for c in db.query(Customer).order_by(Customer.name).all():
        sector = (c.sector or "").strip()
        meter = meters.get(c.meter_id)
        held = possible_leak = False
        if meter is not None:
            block = reading_block(db, meter, now)
            held = bool(block and block.reason == PENDING)
            summary = usage_summary(db, meter, now)
            possible_leak = summary.leak_warning or meter.meter_id in high_use
            if summary.usual_daily_m3 is not None:
                usual.setdefault(sector, []).append(summary.usual_daily_m3 * MONTH_DAYS)
        owed = round(sum(b.outstanding for b in balances(db, c.customer_id).values() if not b.settled), 2)
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
