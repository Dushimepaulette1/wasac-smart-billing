"""The household changed the photo reader's digits: when does that need an officer?

The AI read is not the truth (about 56% of photos are read exactly), so an edit alone never holds a
reading and a matching read never approves one: every rule still runs on the household's value.
Only one case is held: the reader's read was complete and reliable, and the household's value is
ANOMALY_EDIT_HOLD_M3 (1 m³) or more lower. That lowers the bill, and a reliable read rarely misses by
a whole cubic metre. Litre-wheel edits and upward edits are not held for being edits.

"Reliable" reuses what the photo step already decided (app/vision/guidance.py): all 8 digits read,
no CHECK_NUMBERS (a digit the reader was unsure of, or confidence under the calibrated
check_numbers_min_confidence) and no HARD_TO_READ (the quality gate).
"""
from dataclasses import dataclass
from typing import List, Optional

from app.anomaly.config import AnomalyConfig
from app.anomaly.readings import digits_to_m3

UNRELIABLE_CODES = ("CHECK_NUMBERS", "HARD_TO_READ")


def household_digits(reading_m3: float, config: AnomalyConfig) -> str:
    """565.846 -> '00565846': the household's value as meter wheels."""
    return f"{round(reading_m3 * 10 ** config.decimal_digits):0{config.reading_length}d}"


def changed_positions(ai_digits: Optional[str], typed: Optional[str]) -> List[int]:
    """Which wheels (0 = leftmost) differ between the reader's digits and the household's."""
    if not ai_digits or not typed or len(ai_digits) != len(typed):
        return []
    return [i for i, (a, b) in enumerate(zip(ai_digits, typed)) if a != b]


def reader_reliable(reader_digits: Optional[str], guidance: Optional[str], config: AnomalyConfig) -> bool:
    if not reader_digits or len(reader_digits) != config.reading_length or not reader_digits.isdigit():
        return False
    codes = set((guidance or "").split(","))
    return not codes.intersection(UNRELIABLE_CODES)


@dataclass(frozen=True)
class EditCheck:
    ai_digits: Optional[str]
    household_digits: str
    ai_reliable: bool
    lowered_m3: Optional[float]  # how much lower than the AI read the household's value is (negative: higher)
    hold: bool

    def features(self) -> dict:
        return {
            "ai_digits": self.ai_digits,
            "household_digits": self.household_digits,
            "ai_reliable": self.ai_reliable,
            "edited": self.ai_digits is not None and self.ai_digits != self.household_digits,
            "edit_lowered_m3": round(self.lowered_m3, 3) if self.lowered_m3 is not None else None,
        }


def check_edit(reader_digits: Optional[str], guidance: Optional[str], reading_m3: float,
               config: AnomalyConfig) -> EditCheck:
    typed = household_digits(reading_m3, config)
    reliable = reader_reliable(reader_digits, guidance, config)
    lowered = None
    if reliable:
        conversion = digits_to_m3(reader_digits, config)
        lowered = round(conversion.reading_m3 - reading_m3, config.decimal_digits) if conversion.ok else None
    hold = lowered is not None and lowered >= config.edit_hold_m3
    return EditCheck(ai_digits=reader_digits, household_digits=typed, ai_reliable=reliable,
                     lowered_m3=lowered, hold=hold)
