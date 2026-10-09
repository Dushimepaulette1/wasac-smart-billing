import logging
import os
from dataclasses import dataclass
from typing import List, Optional

from anomaly.rules import AnomalyType

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
}


RETAKE_MESSAGE = "WASAC: We could not read your meter reliably. Please retake a clear photo of your water meter."
RESUBMIT_MESSAGE = (
    "WASAC: We could not confirm your last meter reading. Please submit a new, clear photo of your water meter."
)


def confirmed_message(reading_m3: float, amount_rwf: float) -> str:
    return f"WASAC: Your meter reading of {reading_m3:.3f} m3 has been confirmed. Bill: RWF {amount_rwf:,.0f}."


def action_for(anomaly_type: AnomalyType) -> Action:
    return ACTIONS.get(anomaly_type, NO_ACTION)


def message_for(anomaly_type: AnomalyType) -> str:
    return MESSAGES[anomaly_type]


def send_sms(phone: str, message: str) -> bool:
    # TODO: wire Africa's Talking once credentials exist. Read AT_USERNAME and AT_API_KEY from the
    # environment, call africastalking.initialize(username, api_key), then
    # africastalking.SMS.send(message, [phone]). Never hard-code the key.
    configured = bool(os.getenv("AT_USERNAME") and os.getenv("AT_API_KEY"))
    logger.info(
        "[SMS %s] to=%s message=%r",
        "not sent: Africa's Talking not wired yet" if configured else "not sent: AT_USERNAME/AT_API_KEY unset",
        phone,
        message,
    )
    return False


def dispatch(anomaly_type: AnomalyType, phone: Optional[str], message: str) -> List[str]:
    """Perform the actions for this anomaly type. Returns what was done, for logging/response."""
    action = action_for(anomaly_type)
    done = []
    if action.sms_household:
        if phone:
            send_sms(phone, message)
            done.append("sms_household_logged")
        else:
            logger.warning("No phone number on file; cannot SMS household about %s", anomaly_type.value)
    if action.staff_review:
        done.append("staff_dashboard_flag")
    return done
