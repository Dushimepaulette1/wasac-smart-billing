"""Tests."""
from datetime import timedelta
from statistics import median
import pytest
from app.models import AnomalyFlag
from app.anomaly.features import build_periods
from app.anomaly.readings import m3_to_digits
from app.anomaly.rules import AnomalyType
from app.anomaly.service import assess, load_history, score_submission
from app.models import Reading
from support.factories import T0, add_household


DEMO_ID = "DEMO-MTR-001"


def _normal_daily(points):
    return median(p.daily_consumption for p in build_periods(points))


def test_when_a_reading_is_normal_should_not_flag_it(config, demo_histories, demo_model):
    points = demo_histories[DEMO_ID]
    daily = _normal_daily(points)
    when = points[-1].date + timedelta(days=31)
    result = assess(DEMO_ID, points, points[-1].reading_m3 + daily * 31, when, demo_model, config)
    assert result.model_used
    assert not result.is_anomaly
    assert result.anomaly_type == AnomalyType.NORMAL.value


def test_when_a_reading_is_a_spike_should_flag_it(config, demo_histories, demo_model):
    points = demo_histories[DEMO_ID]
    daily = _normal_daily(points)
    when = points[-1].date + timedelta(days=30)
    result = assess(DEMO_ID, points, points[-1].reading_m3 + daily * 4 * 30, when, demo_model, config)
    assert result.is_anomaly
    assert result.anomaly_type == AnomalyType.SPIKE.value
    assert not result.needs_retake


def test_when_a_trained_model_scores_demo_readings_should_pass_normal_and_flag_a_spike(db, config, demo_histories, trained_model_on_disk):
    points = demo_histories[DEMO_ID]
    add_household(db, DEMO_ID, points)
    daily = _normal_daily(points)
    when = points[-1].date + timedelta(days=30)

    normal = score_submission(db, DEMO_ID, m3_to_digits(points[-1].reading_m3 + daily * 30, config), when)
    assert normal.model_used and not normal.is_anomaly and normal.flag_id is None

    spike = score_submission(db, DEMO_ID, m3_to_digits(points[-1].reading_m3 + daily * 5 * 30, config), when)
    assert spike.anomaly_type == AnomalyType.SPIKE.value
    flag = db.get(AnomalyFlag, spike.flag_id)
    assert flag.household_id == DEMO_ID
    assert flag.status == "open" and flag.requires_staff_review
    assert flag.features["ratio_to_median"] > 3


def test_when_the_digit_count_is_wrong_should_ask_for_a_retake_and_log_it(db, config, demo_histories):
    add_household(db, DEMO_ID, demo_histories[DEMO_ID])
    result = score_submission(db, DEMO_ID, "0056584", demo_histories[DEMO_ID][-1].date + timedelta(days=30))
    assert result.needs_retake and result.reading_m3 is None
    assert result.anomaly_type == AnomalyType.MISREAD_SUSPECTED.value
    flag = db.get(AnomalyFlag, result.flag_id)
    assert not flag.requires_staff_review
    assert "Expected 8 digits" in flag.features["conversion_error"]


def test_when_the_household_is_unknown_should_raise(db):
    with pytest.raises(LookupError):
        score_submission(db, "NOPE", "00565846", T0)


@pytest.mark.parametrize("status", ["pending_review", "rejected"])
def test_when_readings_are_unconfirmed_should_leave_them_out_of_history(db, demo_histories, status):
    points = demo_histories[DEMO_ID]
    add_household(db, DEMO_ID, points)
    when = points[-1].date + timedelta(days=30)
    db.add(Reading(meter_id=DEMO_ID, submitted_value=points[-1].reading_m3 + 500,
                   submission_time=when, validation_status=status))
    db.add(Reading(meter_id=DEMO_ID, submitted_value=points[-1].reading_m3 + 9,
                   submission_time=when + timedelta(days=1), validation_status="anomaly_flagged"))
    db.commit()

    history = load_history(db, DEMO_ID, when + timedelta(days=30))
    values = [p.reading_m3 for p in history]
    assert points[-1].reading_m3 + 500 not in values
    assert points[-1].reading_m3 + 9 in values  # confirmed-but-flagged readings stay in history
    assert len(history) == len(points) + 1
