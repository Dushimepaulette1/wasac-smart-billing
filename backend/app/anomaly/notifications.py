import logging
from dataclasses import dataclass
from typing import List, Optional

from app.anomaly.rules import AnomalyType
from app.services.sms import send_sms

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Action:
    sms_household: bool
    staff_review: bool


ACTIONS = {
    AnomalyType.MISREAD_SUSPECTED: Action(sms_household=True, staff_review=True),
    AnomalyType.SPIKE: Action(sms_household=True, staff_review=True),
    AnomalyType.SUSTAINED_HIGH: Action(sms_household=True, staff_review=True),
    AnomalyType.METER_STUCK: Action(sms_household=False, staff_review=True),
    AnomalyType.UNUSUAL: Action(sms_household=False, staff_review=True),
    AnomalyType.LOCATION_CHECK: Action(sms_household=False, staff_review=True),
    AnomalyType.NO_BASELINE: Action(sms_household=False, staff_review=True),
    AnomalyType.EDITED_DOWN: Action(sms_household=False, staff_review=True),
}
NO_ACTION = Action(sms_household=False, staff_review=False)

MESSAGES = {
    AnomalyType.BASELINE: "Thank you. Your first meter reading has been recorded.",
    AnomalyType.NORMAL: "Thank you. Your meter reading has been recorded.",
    AnomalyType.MISREAD_SUSPECTED: (
        "WASAC: Your meter reading does not match your recent readings and is being checked. "
        "We will SMS you if we need a new photo."
    ),
    AnomalyType.SPIKE: (
        "WASAC: Unusually high water use was detected on your meter. "
        "Please check taps, toilets and pipes for leaks. WASAC will confirm the reading before billing. "
        "Call 1580 if you need help."
    ),
    AnomalyType.SUSTAINED_HIGH: (
        "WASAC: Your water use has been higher than normal for several periods. "
        "This can mean a hidden leak. Please check your pipes; WASAC will follow up."
    ),
    AnomalyType.METER_STUCK: "Your reading has been recorded. WASAC may contact you to check your meter.",
    AnomalyType.UNUSUAL: "Your reading has been recorded and will be reviewed by WASAC.",
    AnomalyType.LOCATION_CHECK: (
        "WASAC: We could not confirm this photo was taken at your meter, so an officer will check "
        "the reading before billing."
    ),
    AnomalyType.NO_BASELINE: (
        "WASAC: This is the first reading for your meter. An officer will check it and record it as your "
        "starting point. Your first bill will come with your next reading."
    ),
    AnomalyType.EDITED_DOWN: (
        "WASAC: The reading you sent is lower than what we read in your photo, so an officer will compare "
        "the two before billing."
    ),
}


RETAKE_MESSAGE = "WASAC: We could not read your meter reliably. Please retake a clear photo of your water meter."
RESUBMIT_MESSAGE = (
    "WASAC: We could not confirm your last meter reading. Please submit a new, clear photo of your water meter."
)


def confirmed_message(reading_m3: float, amount_rwf: float) -> str:
    return f"WASAC: Your meter reading of {reading_m3:.3f} m3 has been confirmed. Bill: RWF {amount_rwf:,.0f}."


def starting_point_message(reading_m3: float) -> str:
    return (f"WASAC: Your first meter reading of {reading_m3:.3f} m3 is recorded as your starting point. "
            "Your first bill will come with your next reading.")


def action_for(anomaly_type: AnomalyType) -> Action:
    return ACTIONS.get(anomaly_type, NO_ACTION)


def message_for(anomaly_type: AnomalyType) -> str:
    return MESSAGES[anomaly_type]


def sms_household(phone: str, message: str) -> str:
    """Send the SMS; the action to report says whether Africa's Talking took it."""
    return "sms_household_sent" if send_sms(phone, message) else "sms_household_not_sent"


def dispatch(anomaly_type: AnomalyType, phone: Optional[str], message: str) -> List[str]:
    """Perform the actions for this anomaly type. Returns what was done, for logging/response."""
    action = action_for(anomaly_type)
    done = []
    if action.sms_household:
        if phone:
            done.append(sms_household(phone, message))
        else:
            logger.warning("No phone number on file; cannot SMS household about %s", anomaly_type.value)
    if action.staff_review:
        done.append("staff_dashboard_flag")
    return done
