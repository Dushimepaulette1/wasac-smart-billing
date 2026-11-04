"""The leak alert and the next-bill estimate (app/services/usage.py)."""
from datetime import timedelta

import pytest

from app.models import Meter, Reading
from app.services.billing import calculate_bill, tariff
from app.services.usage import NOT_ENOUGH_HISTORY, UsageError, usage_summary
from support.factories import T0, add_household, make_history


def summary(db, dailies, days=30, after=1, meter_now=None, **kw):
    """A household with these daily uses; asked `after` days after its newest reading."""
    points = make_history(dailies, days=days)
    add_household(db, "MTR-1", points)
    meter = db.get(Meter, "MTR-1")
    return usage_summary(db, meter, now=points[-1].date + timedelta(days=after), meter_now=meter_now, **kw)


def test_when_the_meter_has_only_its_first_reading_should_give_no_numbers(db):
    s = summary(db, [])
    assert s.reason == NOT_ENOUGH_HISTORY
    assert s.projected_amount is None and not s.leak_warning


def test_when_the_newest_period_is_high_but_there_are_fewer_than_three_earlier_ones_should_not_warn(db):
    assert not summary(db, [0.5, 0.5, 1.0]).leak_warning


def test_when_use_is_as_usual_should_not_warn(db):
    assert not summary(db, [0.5, 0.6, 0.5, 0.55]).leak_warning


def test_when_the_newest_period_is_well_above_usual_should_warn_with_the_percent(db):
    s = summary(db, [0.5, 0.5, 0.5, 0.8])  # 1.6x, 9 m3 more over 30 days
    assert s.leak_warning
    assert s.percent_above_usual == 60
    newest = db.query(Reading).order_by(Reading.submission_time.desc()).first()
    assert s.leak_reading_id == newest.reading_id


def test_when_the_newest_period_is_high_but_only_by_a_little_water_should_not_warn(db):
    # 1.6x, but 0.03 m3/day over 30 days is 0.9 m3, under the 3 m3 minimum: not worth an alert.
    assert not summary(db, [0.05, 0.05, 0.05, 0.08]).leak_warning


def test_when_the_high_period_ended_long_ago_should_not_warn(db):
    assert not summary(db, [0.5, 0.5, 0.5, 0.8], after=50).leak_warning


def test_when_a_lower_reading_reset_the_meter_should_start_the_history_again(db):
    points = make_history([0.5, 0.5, 0.5])
    reset = points[-1].date + timedelta(days=30)
    points += [type(points[0])(reset, 10.0), type(points[0])(reset + timedelta(days=30), 34.0)]
    add_household(db, "MTR-1", points)
    s = usage_summary(db, db.get(Meter, "MTR-1"), now=points[-1].date + timedelta(days=1))
    # Only the period after the reset counts: no earlier periods, so no alert, and 0.8 m3/day is usual.
    assert not s.leak_warning
    assert s.usual_daily_m3 == pytest.approx(0.8)


def test_the_estimate_should_price_the_usual_use_with_todays_tariff(db):
    s = summary(db, [20 / 30] * 4)  # 20 m3 a month
    assert s.projected_m3 == 20.0
    assert s.tariff_version == tariff()["version"]
    assert s.projected_amount == round(calculate_bill(20.0, s.tariff_version)["total"])
    assert s.projected_on == T0 + timedelta(days=150)
    assert not s.used_meter_now


def test_when_todays_number_is_higher_than_usual_should_raise_the_estimate_and_warn(db):
    points = make_history([0.5] * 4)
    # 10 m3 in 5 days, against a usual 0.5 m3/day.
    s = summary(db, [0.5] * 4, after=5, meter_now=points[-1].reading_m3 + 10)
    assert s.used_meter_now and s.used_so_far_m3 == 10.0
    assert s.projected_m3 == 60.0  # 10 so far, then 25 days at 2 m3/day
    assert s.leak_so_far


def test_when_todays_number_is_normal_should_estimate_from_it_without_a_warning(db):
    points = make_history([0.5] * 4)
    s = summary(db, [0.5] * 4, after=10, meter_now=points[-1].reading_m3 + 4)
    assert s.used_meter_now
    assert s.projected_m3 == 14.0  # 4 so far, then 20 days at the usual 0.5
    assert not s.leak_so_far


def test_when_todays_number_is_lower_than_the_last_reading_should_refuse_it(db):
    points = make_history([0.5] * 4)
    with pytest.raises(UsageError, match="lower than your last reading"):
        summary(db, [0.5] * 4, after=5, meter_now=points[-1].reading_m3 - 1)


def test_when_it_is_too_soon_after_the_last_reading_should_estimate_from_usual_use(db):
    points = make_history([0.5] * 4)
    s = summary(db, [0.5] * 4, after=1, meter_now=points[-1].reading_m3 + 3)
    assert not s.used_meter_now
    assert s.projected_m3 == 15.0


def test_pending_and_rejected_readings_should_not_count(db):
    points = make_history([0.5] * 4)
    add_household(db, "MTR-1", points)
    later = points[-1].date + timedelta(days=30)
    db.add(Reading(meter_id="MTR-1", submitted_value=points[-1].reading_m3 + 60, submission_time=later,
                   validation_status="pending_review"))
    db.commit()
    s = usage_summary(db, db.get(Meter, "MTR-1"), now=later + timedelta(days=1))
    assert not s.leak_warning
    assert s.last_reading_m3 == points[-1].reading_m3


def test_when_the_reading_is_overdue_should_estimate_every_day_since_the_last_one(db):
    s = summary(db, [0.5] * 4, after=45)
    assert s.projected_m3 == 22.5  # 45 days at 0.5, not a usual 30
    assert s.projected_on == T0 + timedelta(days=120 + 45)
