import pytest

from anomaly.readings import digits_to_m3, m3_to_digits


def test_eight_digits_convert_to_m3(config):
    result = digits_to_m3("00565846", config)
    assert result.ok and not result.needs_retake
    assert result.reading_m3 == pytest.approx(565.846)


def test_leading_and_trailing_zeros(config):
    assert digits_to_m3("00000000", config).reading_m3 == 0.0
    assert digits_to_m3("12345000", config).reading_m3 == pytest.approx(12345.0)


@pytest.mark.parametrize("digits", ["0056584", "005658467", "", "565846"])
def test_wrong_length_needs_retake_not_silent_conversion(config, digits):
    result = digits_to_m3(digits, config)
    assert not result.ok
    assert result.needs_retake
    assert result.reading_m3 is None


def test_non_digits_need_retake(config):
    result = digits_to_m3("0056a846", config)
    assert result.needs_retake and result.reading_m3 is None


def test_round_trip(config):
    assert m3_to_digits(565.846, config) == "00565846"
    assert digits_to_m3(m3_to_digits(1234.5, config), config).reading_m3 == pytest.approx(1234.5)
