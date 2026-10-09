import math
from datetime import timedelta

import pytest
from conftest import make_history

from anomaly.features import compute_features
from anomaly.rules import AnomalyType, apply_rules, classify_model_anomaly, is_cold_start
from anomaly.service import assess


def next_reading(history, daily, days=30):
    last = history[-1]
    return last.reading_m3 + daily * days, last.date + timedelta(days=days)


# --- features -------------------------------------------------------------

def test_irregular_dates_are_normalised_per_day(config):
    history = make_history([0.6, 0.6, 0.6, 0.6], days=[20, 41, 27, 35])
    m3, when = next_reading(history, 0.6, days=52)
    f = compute_features(history, m3, when, config)
    assert f.days_since_last == pytest.approx(52)
    assert f.consumption_m3 == pytest.approx(0.6 * 52, abs=1e-3)
    assert f.daily_consumption == pytest.approx(0.6, abs=1e-3)
    assert f.ratio_to_median == pytest.approx(1.0, abs=0.01)
    assert f.ratio_to_recent == pytest.approx(1.0, abs=0.01)
    assert f.n_history == 4


def test_same_day_resubmission_uses_minimum_one_day(config):
    history = make_history([0.6, 0.6, 0.6])
    last = history[-1]
    f = compute_features(history, last.reading_m3 + 0.3, last.date + timedelta(hours=2), config)
    assert f.days_since_last == 1.0
    assert f.daily_consumption == pytest.approx(0.3)


def test_zero_mad_does_not_divide_by_zero(config):
    history = make_history([0.5, 0.5, 0.5, 0.5])
    m3, when = next_reading(history, 0.8)
    f = compute_features(history, m3, when, config)
    assert math.isfinite(f.robust_z) and f.robust_z > 0
    assert all(math.isfinite(v) for v in f.model_vector())


def test_first_submission_has_no_features(config):
    assert compute_features([], 500.0, make_history([])[0].date, config) is None


# --- rules ----------------------------------------------------------------

def test_first_submission_is_baseline_not_anomaly(config):
    point = make_history([])[0]
    result = assess("H1", [], point.reading_m3, point.date, None, config)
    assert result.anomaly_type == AnomalyType.BASELINE.value
    assert not result.is_anomaly and not result.needs_retake


def test_backwards_reading_is_suspected_misread(config):
    history = make_history([0.6] * 5)
    result = assess("H1", history, history[-1].reading_m3 - 3, history[-1].date + timedelta(days=30), None, config)
    assert result.anomaly_type == AnomalyType.MISREAD_SUSPECTED.value
    assert result.is_anomaly and result.pending_review
    assert not result.needs_retake  # the reading is usable; staff decide, the household is told it is being checked


def test_above_hard_maximum_is_spike_even_in_cold_start(config):
    history = make_history([0.6])
    m3, when = next_reading(history, config.max_daily_m3 + 1)
    result = assess("H1", history, m3, when, None, config)
    assert result.anomaly_type == AnomalyType.SPIKE.value


def test_zero_consumption_over_threshold_is_meter_stuck(config):
    history = make_history([0.6, 0.6, 0.6, 0.0], days=[30, 30, 30, 16])
    m3, when = next_reading(history, 0.0, days=16)  # 32 zero days across two periods
    f = compute_features(history, m3, when, config)
    assert f.zero_streak_days == pytest.approx(32)
    assert apply_rules(f, config) == AnomalyType.METER_STUCK


def test_short_zero_period_is_not_stuck(config):
    history = make_history([0.6, 0.6, 0.6])
    m3, when = next_reading(history, 0.0, days=20)
    assert apply_rules(compute_features(history, m3, when, config), config) is None


def test_cold_start_uses_rules_only_even_with_a_model(config, demo_model):
    history = make_history([0.6, 0.6])  # 2 previous periods < 3
    m3, when = next_reading(history, 2.5)  # 4x normal, but under the hard max
    f = compute_features(history, m3, when, config)
    assert is_cold_start(f, config)
    result = assess("H1", history, m3, when, demo_model, config)
    assert result.anomaly_type == AnomalyType.NORMAL.value
    assert not result.model_used and result.features["cold_start"]


# --- classification of model-flagged periods ----------------------------

def _features_for(config, dailies, new_daily):
    history = make_history(dailies)
    m3, when = next_reading(history, new_daily)
    return compute_features(history, m3, when, config)


def test_ten_times_normal_looks_like_digit_error(config):
    f = _features_for(config, [0.4] * 6, 4.0)
    assert classify_model_anomaly(f, config) == AnomalyType.MISREAD_SUSPECTED


def test_three_to_ten_times_is_spike(config):
    f = _features_for(config, [0.4] * 6, 1.6)
    assert classify_model_anomaly(f, config) == AnomalyType.SPIKE


def test_three_high_periods_in_a_row_is_sustained_high(config):
    f = _features_for(config, [0.4] * 8 + [0.8, 0.8], 0.8)
    assert classify_model_anomaly(f, config) == AnomalyType.SUSTAINED_HIGH


def test_other_model_flags_are_unusual(config):
    f = _features_for(config, [0.4] * 6, 0.1)
    assert classify_model_anomaly(f, config) == AnomalyType.UNUSUAL
