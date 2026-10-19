"""Rwandan mobile numbers (app/utils/phone.py)."""
import pytest
from app.utils.phone import normalize_phone


PHONE = "+250788000111"  # add_household's default


@pytest.mark.parametrize("raw", ["0788000111", "788000111", "+250 788 000 111", "250-788-000-111", "(078) 800-0111"])
def test_when_a_number_is_written_differently_should_normalize_it(raw):
    assert normalize_phone(raw) == PHONE


@pytest.mark.parametrize("raw", ["", "12345", "0588000111", "+254712345678", "07880001110", "abc"])
def test_when_a_number_is_not_a_rwandan_mobile_should_refuse_it(raw):
    assert normalize_phone(raw) is None
