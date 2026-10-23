"""Meter values typed by people: plain digits only.

float() alone would also take "nan", "inf", "1e3" and " 12_5 ", which are not readings.
"""
import re
from typing import Optional

MAX_READING_M3 = 99_999.999  # 5 black wheels, 3 red

_DECIMAL = re.compile(r"[0-9]{1,5}([.,][0-9]{1,3})?")


def parse_meter_value(typed: str) -> Optional[float]:
    """'00565.846', '565.846', '565,846' or '565' -> m3; anything else -> None."""
    typed = (typed or "").strip()
    if not _DECIMAL.fullmatch(typed):
        return None
    return float(typed.replace(",", "."))
