"""Rule-based history check (no model needed): daily use far above the household's own median is
held for an officer. Thresholds are provisional (app/anomaly/config.py)."""
from datetime import timedelta

import pytest

from app.anomaly.config import AnomalyConfig
from app.anomaly.rules import AnomalyType
from app.anomaly.service import assess
from support.factories import make_history

CFG = AnomalyConfig()  # spike_ratio 3.0, min_history_periods 3, min_period_days 7


def judge(points, daily, days=30, model=None, config=CFG):
    when = points[-1].date + timedelta(days=days)
    return assess("H", points, points[-1].reading_m3 + daily * days, when, model, config)


@pytest.mark.parametrize("daily, expected, held", [
    (0.40, "NORMAL", False),
    (0.80, "NORMAL", False),            # twice the usual: not held
    (1.21, "NORMAL", False),            # just under 3x
    (1.22, "SPIKE", True),              # 3x: (1.22 + 0.01) / (0.40 + 0.01) = 3.0
    (1.60, "SPIKE", True),
    (4.00, "MISREAD_SUSPECTED", True),  # about 10x: a shifted digit, not water use
])
def test_when_use_is_compared_with_the_households_usual_should_hold_from_3x(daily, expected, held):
    # Ratios add 10 litres/day to both sides (features.EPS_DAILY_M3), so households with near-zero
    # use do not give infinite ratios: "3x a 0.40 m3/day median" is 1.22 m3/day.
    points = make_history([0.4] * 4)
    result = judge(points, daily)
    assert result.anomaly_type == expected and result.pending_review == held
    assert result.features["insufficient_history"] is False


def test_when_there_are_fewer_than_three_suitable_periods_should_not_hold_by_ratio():
    points = make_history([0.4] * 2)  # two periods
    result = judge(points, 0.4 * 4)
    assert result.anomaly_type == "NORMAL" and result.features["insufficient_history"] is True


def test_when_past_periods_are_shorter_than_a_week_should_not_count_them():
    points = make_history([0.4] * 5, days=[30, 30, 3, 3, 3])  # two suitable periods only
    result = judge(points, 0.4 * 4)
    assert result.anomaly_type == "NORMAL" and result.features["n_suitable_periods"] == 2


def test_when_this_reading_comes_within_a_week_should_not_compare_its_daily_rate():
    points = make_history([0.4] * 4)
    result = judge(points, 0.4 * 4, days=3)
    assert result.anomaly_type == "NORMAL" and result.features["insufficient_history"] is True


def test_when_the_threshold_is_configured_should_use_it(monkeypatch):
    monkeypatch.setenv("ANOMALY_SPIKE_RATIO", "5")
    points = make_history([0.4] * 4)
    assert judge(points, 0.4 * 4, config=AnomalyConfig.from_env()).anomaly_type == "NORMAL"
    assert judge(points, 0.4 * 6, config=AnomalyConfig.from_env()).anomaly_type == "SPIKE"


def test_when_the_daily_limit_is_exceeded_should_still_be_a_spike_without_history():
    points = make_history([0.4])  # one period: cold start
    assert judge(points, 6.0).anomaly_type == AnomalyType.SPIKE.value


def test_when_the_model_is_loaded_should_still_apply_the_rule_first(demo_model):
    points = make_history([0.4] * 6)
    result = judge(points, 0.4 * 4, model=demo_model)
    assert result.anomaly_type == "SPIKE" and not result.model_used
