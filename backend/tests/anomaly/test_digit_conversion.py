"""Tests."""
import pytest
from app.anomaly.readings import digits_to_m3, m3_to_digits


def test_when_given_eight_digits_should_convert_to_cubic_metres(config):
    result = digits_to_m3("00565846", config)
    assert result.ok and not result.needs_retake
    assert result.reading_m3 == pytest.approx(565.846)


def test_when_digits_have_leading_or_trailing_zeros_should_keep_their_value(config):
    assert digits_to_m3("00000000", config).reading_m3 == 0.0
    assert digits_to_m3("12345000", config).reading_m3 == pytest.approx(12345.0)


@pytest.mark.parametrize("digits", ["0056584", "005658467", "", "565846"])
def test_when_the_digit_count_is_wrong_should_ask_for_a_retake_not_guess(config, digits):
    result = digits_to_m3(digits, config)
    assert not result.ok
    assert result.needs_retake
    assert result.reading_m3 is None


def test_when_the_text_is_not_digits_should_ask_for_a_retake(config):
    result = digits_to_m3("0056a846", config)
    assert result.needs_retake and result.reading_m3 is None


def test_when_converting_to_cubic_metres_and_back_should_get_the_same_digits(config):
    assert m3_to_digits(565.846, config) == "00565846"
    assert digits_to_m3(m3_to_digits(1234.5, config), config).reading_m3 == pytest.approx(1234.5)
