from dataclasses import dataclass
from typing import Optional

from app.anomaly.config import AnomalyConfig


@dataclass(frozen=True)
class ConversionResult:
    ok: bool
    reading_m3: Optional[float] = None
    needs_retake: bool = False
    reason: str = ""


def digits_to_m3(digits: str, config: AnomalyConfig) -> ConversionResult:
    """Convert CRNN wheel digits to m3: first (length - decimals) wheels are m3, the rest litres.

    Wrong-length or non-digit input is never coerced; it comes back as a retake request.
    """
    cleaned = (digits or "").strip()
    if not cleaned.isdigit():
        return ConversionResult(
            ok=False, needs_retake=True, reason=f"Reading '{digits}' contains non-digit characters."
        )
    if len(cleaned) != config.reading_length:
        return ConversionResult(
            ok=False,
            needs_retake=True,
            reason=(
                f"Expected {config.reading_length} digits but read {len(cleaned)} "
                f"('{cleaned}'). A digit was probably dropped or duplicated."
            ),
        )

    split = config.reading_length - config.decimal_digits
    whole = int(cleaned[:split])
    fraction = int(cleaned[split:]) / (10 ** config.decimal_digits) if config.decimal_digits else 0.0
    return ConversionResult(ok=True, reading_m3=round(whole + fraction, config.decimal_digits))


REGISTER_M3 = 100_000.0     # the 5 black wheels turn over to 00000 after 99999.999
ROLLOVER_FROM_M3 = 99_000.0  # a previous reading this close to the top
ROLLOVER_TO_M3 = 1_000.0     # and a new reading this close to zero


def rollover_consumption(previous_m3: float, reading_m3: float) -> Optional[float]:
    """The use across a register turning over (99,950 then 00,010 is 60 m3), or None if this does
    not look like one. It is rare (decades of use), so an officer always confirms it."""
    if previous_m3 >= ROLLOVER_FROM_M3 and reading_m3 < ROLLOVER_TO_M3:
        return round(REGISTER_M3 - previous_m3 + reading_m3, 3)
    return None


def m3_to_digits(reading_m3: float, config: AnomalyConfig) -> str:
    """Inverse of digits_to_m3, used by the evaluation script to inject digit errors."""
    scaled = round(reading_m3 * (10 ** config.decimal_digits))
    return str(scaled).zfill(config.reading_length)
