"""Typed meter values (app/utils/meter_value.py)."""
import pytest

from app.utils.meter_value import parse_meter_value


@pytest.mark.parametrize("typed, value", [
    ("00565.846", 565.846), ("565.846", 565.846), ("565,846", 565.846), (" 565 ", 565.0), ("99999.999", 99_999.999),
])
def test_when_plain_digits_are_typed_should_read_them(typed, value):
    assert parse_meter_value(typed) == pytest.approx(value)


@pytest.mark.parametrize("typed", [
    "nan", "NaN", "inf", "-inf", "1e3", "-1", "12_5", "", "565.8461", "100000", ".5", "5.", "0x10", "١٢٣",
])
def test_when_anything_else_is_typed_should_refuse_it(typed):
    assert parse_meter_value(typed) is None
