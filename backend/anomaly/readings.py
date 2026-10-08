from dataclasses import dataclass
from typing import Optional

from anomaly.config import AnomalyConfig


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


def m3_to_digits(reading_m3: float, config: AnomalyConfig) -> str:
    """Inverse of digits_to_m3, used by the evaluation script to inject digit errors."""
    scaled = round(reading_m3 * (10 ** config.decimal_digits))
    return str(scaled).zfill(config.reading_length)
