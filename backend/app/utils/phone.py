"""Rwandan mobile numbers."""
import re
from typing import Optional


def normalize_phone(raw: str) -> Optional[str]:
    """A Rwandan mobile number as +2507XXXXXXXX, or None.
    Accepts 0788 123 456, 788123456, 250788123456 and +250 788-123-456."""
    digits = re.sub(r"[\s\-().]", "", raw or "")
    if digits.startswith("+"):
        digits = digits[1:]
    if not digits.isdigit():
        return None
    if digits.startswith("250"):
        digits = digits[3:]
    elif digits.startswith("0"):
        digits = digits[1:]
    return f"+250{digits}" if re.fullmatch(r"7\d{8}", digits) else None
