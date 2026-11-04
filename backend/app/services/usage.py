"""A household's usual water use: a leak alert after a bill, and an estimate of the next bill.

Both come from the meter's confirmed readings (app/anomaly/scoring.py load_history: pending and
rejected readings never count, and history starts again after a reset). Only periods of at least
AnomalyConfig.min_period_days are compared, as in the rule-based history check.

    Leak alert  the newest billed period's daily use is leak_ratio x the household's usual (the
                median of the earlier periods) and at least leak_min_extra_m3 above it. It only
                tells the household; it never holds a reading (that is spike_ratio's job).
    Estimate    the usual daily use over a usual period (or over every day since the last reading,
                if that is longer), priced with today's tariff. With a number
                the household typed today (meter_now), the use so far plus the rest of the period
                at the higher of the usual rate and the rate so far. Nothing is stored.

The thresholds are provisional, like every other check (app/anomaly/README.md "Thresholds").
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import median
from typing import List, Optional

from sqlalchemy.orm import Session

from app.anomaly.config import AnomalyConfig
from app.anomaly.features import Period, ReadingPoint, build_periods
from app.anomaly.notifications import leak_message, sms_household
from app.anomaly.scoring import load_history
from app.anomaly.statuses import NOT_CONFIRMED
from app.models import Customer, Meter, Reading
from app.services.billing import calculate_bill, tariff

NOT_ENOUGH_HISTORY = "not_enough_history"
DEFAULT_PERIOD_DAYS = 30.0
# An alert about a period that ended longer ago than this is no longer news.
LEAK_ALERT_DAYS = 45
# Fewer days since the last reading than this give a daily rate too noisy to project from.
MIN_DAYS_SO_FAR = 3.0


class UsageError(Exception):
    """A number the household typed cannot be used (the API answers 422 with this message)."""


@dataclass
class UsageSummary:
    reason: Optional[str] = None
    usual_daily_m3: Optional[float] = None
    usual_period_days: Optional[float] = None
    last_reading_m3: Optional[float] = None
    last_reading_date: Optional[datetime] = None
    projected_m3: Optional[float] = None
    projected_amount: Optional[float] = None
    projected_on: Optional[datetime] = None
    tariff_version: Optional[str] = None
    used_meter_now: bool = False
    used_so_far_m3: Optional[float] = None
    leak_warning: bool = False
    leak_reading_id: Optional[int] = None
    percent_above_usual: Optional[int] = None
    leak_so_far: bool = False


def _suitable(periods: List[Period], config: AnomalyConfig) -> List[Period]:
    return [p for p in periods if p.days >= config.min_period_days]


def _is_leak(daily: float, days: float, usual: float, config: AnomalyConfig) -> bool:
    """Far enough above the usual rate, and by enough water that it is not just a busy month."""
    return usual > 0 and daily >= config.leak_ratio * usual and (daily - usual) * days >= config.leak_min_extra_m3


def _newest_reading_id(db: Session, meter_id: str) -> Optional[int]:
    return (
        db.query(Reading.reading_id)
        .filter(Reading.meter_id == meter_id, Reading.validation_status.notin_(NOT_CONFIRMED))
        .order_by(Reading.submission_time.desc(), Reading.reading_id.desc())
        .limit(1)
        .scalar()
    )


def _leak(db: Session, meter: Meter, periods: List[Period], points: List[ReadingPoint], now: datetime,
          config: AnomalyConfig, summary: UsageSummary) -> None:
    """Fill in the leak alert for the newest period, if it has one."""
    if not periods or now - points[-1].date > timedelta(days=LEAK_ALERT_DAYS):
        return
    latest = periods[-1]
    earlier = _suitable(periods[:-1], config)
    if latest.days < config.min_period_days or len(earlier) < config.min_history_periods:
        return
    usual = median(p.daily_consumption for p in earlier)
    if not _is_leak(latest.daily_consumption, latest.days, usual, config):
        return
    summary.leak_warning = True
    summary.leak_reading_id = _newest_reading_id(db, meter.meter_id)
    summary.percent_above_usual = round((latest.daily_consumption / usual - 1) * 100)


def usage_summary(db: Session, meter: Meter, now: Optional[datetime] = None,
                  meter_now: Optional[float] = None, config: Optional[AnomalyConfig] = None) -> UsageSummary:
    """The leak alert and the estimate for this meter. meter_now: a number read today, in m3."""
    now = now or datetime.utcnow()
    config = config or AnomalyConfig.from_env()
    points = load_history(db, meter.meter_id, before=now + timedelta(seconds=1))
    periods = build_periods(points)
    suitable = _suitable(periods, config)
    if not suitable:
        return UsageSummary(reason=NOT_ENOUGH_HISTORY)

    last = points[-1]
    usual = median(p.daily_consumption for p in suitable)
    period_days = median(p.days for p in suitable) or DEFAULT_PERIOD_DAYS
    days_so_far = max((now - last.date).total_seconds() / 86400.0, 0.0)
    # A reading that is overdue covers all the days since the last one, not just a usual period.
    span = max(period_days, days_so_far)
    summary = UsageSummary(
        usual_daily_m3=round(usual, 3),
        usual_period_days=round(period_days, 1),
        last_reading_m3=last.reading_m3,
        last_reading_date=last.date,
        projected_on=last.date + timedelta(days=span),
    )
    _leak(db, meter, periods, points, now, config, summary)

    projected = usual * span
    if meter_now is not None:
        if meter_now < last.reading_m3 - 0.0005:
            raise UsageError("This number is lower than your last reading. Check the digits.")
        if days_so_far >= MIN_DAYS_SO_FAR:
            used = round(meter_now - last.reading_m3, 3)
            rate = used / days_so_far
            projected = used + max(rate, usual) * (span - days_so_far)
            summary.used_meter_now = True
            summary.used_so_far_m3 = used
            summary.leak_so_far = (len(suitable) >= config.min_history_periods
                                   and _is_leak(rate, days_so_far, usual, config))

    rates = tariff()
    summary.projected_m3 = round(projected, 1)
    summary.projected_amount = round(calculate_bill(summary.projected_m3, rates["version"])["total"])
    summary.tariff_version = rates["version"]
    return summary


def notify_leak(db: Session, meter_id: str, reading_id: Optional[int]) -> Optional[str]:
    """After a bill for reading_id is committed: if that period looks like a leak, SMS the household
    once (one bill per reading, so once per period). A failed SMS never affects the bill."""
    if reading_id is None:
        return None
    meter = db.get(Meter, meter_id)
    if meter is None:
        return None
    summary = usage_summary(db, meter)
    if not summary.leak_warning or summary.leak_reading_id != reading_id:
        return None
    phone = db.query(Customer.phone).filter(Customer.meter_id == meter_id).scalar()
    if not phone:
        return None
    return sms_household(phone, leak_message(summary.percent_above_usual or 0))
