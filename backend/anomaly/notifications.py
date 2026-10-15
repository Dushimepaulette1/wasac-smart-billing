import logging
import os

import httpx
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
    AnomalyType.LOCATION_CHECK: Action(sms_household=False, staff_review=True),
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


SANDBOX_URL = "https://api.sandbox.africastalking.com/version1/messaging"
LIVE_URL = "https://api.africastalking.com/version1/messaging"
SMS_TIMEOUT_SECONDS = 10
_SUCCESS_CODES = {100, 101, 102}  # Processed, Sent, Queued


def sms_configured() -> bool:
    return bool(os.getenv("AT_USERNAME") and os.getenv("AT_API_KEY"))


def _masked(phone: str) -> str:
    """+250788123456 -> +250788***456: enough to tell messages apart in logs."""
    return phone[:7] + "***" + phone[-3:] if len(phone) > 10 else "***"


def send_sms(phone: str, message: str, *, sensitive: bool = False) -> bool:
    """Send one SMS with Africa's Talking. Returns True if it was accepted.

    AT_USERNAME "sandbox" uses the sandbox: messages appear in the Africa's Talking simulator
    (https://simulator.africastalking.com), not on real phones, and cost nothing. Any other
    username is the live service. AT_SENDER_ID is optional (an approved sender name).
    Without AT_USERNAME/AT_API_KEY nothing is sent and the message is only logged.
    The API key, and with sensitive=True (sign-in codes) the text, are never logged.
    """
    shown = "[hidden: contains a sign-in code]" if sensitive else message
    if not sms_configured():
        logger.info("[SMS not sent: AT_USERNAME/AT_API_KEY unset] to=%s message=%r", _masked(phone), shown)
        return False

    username = os.getenv("AT_USERNAME", "")
    form = {"username": username, "to": phone, "message": message}
    if os.getenv("AT_SENDER_ID"):
        form["from"] = os.getenv("AT_SENDER_ID")
    try:
        response = httpx.post(
            SANDBOX_URL if username == "sandbox" else LIVE_URL,
            data=form,
            headers={"apiKey": os.getenv("AT_API_KEY", ""), "Accept": "application/json"},
            timeout=SMS_TIMEOUT_SECONDS,
        )
        recipients = response.json().get("SMSMessageData", {}).get("Recipients", []) if response.is_success else []
    except (httpx.HTTPError, ValueError) as e:
        logger.warning("[SMS failed] to=%s (%s)", _masked(phone), type(e).__name__)
        return False
    status = recipients[0] if recipients else {}
    ok = status.get("statusCode") in _SUCCESS_CODES
    if ok:
        logger.info("[SMS sent] to=%s message=%r", _masked(phone), shown)
    else:
        # Africa's Talking's own words (e.g. InvalidPhoneNumber, InsufficientBalance); never the key.
        logger.warning("[SMS failed] to=%s http=%s status=%s", _masked(phone), response.status_code,
                       status.get("status") or "no recipient in answer")
    return ok

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
