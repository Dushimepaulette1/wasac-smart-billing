"""Send an SMS with Africa's Talking.

AT_USERNAME "sandbox" uses the free sandbox (messages appear in the Africa's Talking simulator, not
on real phones); any other username is the live service. Unset: messages are only logged.
Numbers are masked in logs; the API key and sign-in codes are never logged.

Sandbox messages are also kept in the sms_outbox table (app/models/sms_outbox.py), which admins
read on the staff "Sent SMS" page: the sandbox simulator is not always available.
SMS_OUTBOX=0 turns that off; live messages are never stored.
"""
import logging
import os

import httpx

logger = logging.getLogger(__name__)

SANDBOX_URL = "https://api.sandbox.africastalking.com/version1/messaging"

LIVE_URL = "https://api.africastalking.com/version1/messaging"

SMS_TIMEOUT_SECONDS = 10

_SUCCESS_CODES = {100, 101, 102}  # Processed, Sent, Queued


def _at_settings() -> tuple[str, str]:
    """(username, key), trimmed: a pasted value often carries a space or a line break.
    The sandbox username is always "sandbox", whatever the capitals."""
    username = os.getenv("AT_USERNAME", "").strip()
    if username.lower() == "sandbox":
        username = "sandbox"
    return username, os.getenv("AT_API_KEY", "").strip()


def sms_configured() -> bool:
    username, key = _at_settings()
    return bool(username and key)


def _masked(phone: str) -> str:
    """+250788123456 -> +250788***456: enough to tell messages apart in logs."""
    return phone[:7] + "***" + phone[-3:] if len(phone) > 10 else "***"


def send_sms(phone: str, message: str, *, sensitive: bool = False) -> bool:
    """Send one SMS with Africa's Talking. Returns True if it was accepted.

    AT_USERNAME "sandbox" uses the sandbox: messages appear in the Africa's Talking simulator
    (https://simulator.africastalking.com) and on the staff "Sent SMS" page, not on real phones,
    and cost nothing. Any other
    username is the live service. AT_SENDER_ID is optional (an approved sender name).
    Without AT_USERNAME/AT_API_KEY nothing is sent and the message is only logged.
    The API key, and with sensitive=True (sign-in codes) the text, are never logged.
    """
    shown = "[hidden: contains a sign-in code]" if sensitive else message
    if not sms_configured():
        logger.info("[SMS not sent: AT_USERNAME/AT_API_KEY unset] to=%s message=%r", _masked(phone), shown)
        return False

    username, key = _at_settings()
    form = {"username": username, "to": phone, "message": message}
    if os.getenv("AT_SENDER_ID"):
        form["from"] = os.getenv("AT_SENDER_ID")
    try:
        response = httpx.post(
            SANDBOX_URL if username == "sandbox" else LIVE_URL,
            data=form,
            headers={"apiKey": key, "Accept": "application/json"},
            timeout=SMS_TIMEOUT_SECONDS,
        )
        recipients = response.json().get("SMSMessageData", {}).get("Recipients", []) if response.is_success else []
    except (httpx.HTTPError, ValueError) as e:
        logger.warning("[SMS failed] to=%s (%s)", _masked(phone), type(e).__name__)
        if username == "sandbox":
            _keep_in_outbox(phone, message, f"not sent ({type(e).__name__})")
        return False
    status = recipients[0] if recipients else {}
    ok = status.get("statusCode") in _SUCCESS_CODES
    if ok:
        logger.info("[SMS sent] to=%s message=%r", _masked(phone), shown)
    else:
        # Africa's Talking's own words (e.g. InvalidPhoneNumber, or for a 401 "The supplied
        # authentication is invalid"); their answers never contain the key.
        reason = status.get("status") or " ".join(response.text.split())[:120] or "empty answer"
        logger.warning("[SMS failed] to=%s http=%s service=%s reason=%s", _masked(phone), response.status_code,
                       "sandbox" if username == "sandbox" else "live", reason)
    if username == "sandbox":
        _keep_in_outbox(phone, message, "sent" if ok else reason)
    return ok


def _outbox_session():
    """A database session for the outbox (tests replace this with their own database)."""
    from app.db.session import SessionLocal

    return SessionLocal()


def _keep_in_outbox(phone: str, message: str, status: str) -> None:
    """Store a sandbox message for the staff "Sent SMS" page; keep only the newest ones.
    A failure here never affects sending."""
    if os.getenv("SMS_OUTBOX", "1") == "0":
        return
    from app.models import SmsOutbox

    try:
        keep = max(1, int(os.getenv("SMS_OUTBOX_KEEP", "200")))
    except ValueError:
        keep = 200
    db = _outbox_session()
    try:
        db.add(SmsOutbox(phone=phone, message=message[:480], status=status[:40]))
        db.flush()
        old = [i for (i,) in db.query(SmsOutbox.id).order_by(SmsOutbox.id.desc()).offset(keep).all()]
        if old:
            db.query(SmsOutbox).filter(SmsOutbox.id.in_(old)).delete(synchronize_session=False)
        db.commit()
    except Exception as e:  # noqa: BLE001 - storing a copy must never break sending
        db.rollback()
        logger.warning("[SMS outbox] could not store a copy (%s)", type(e).__name__)
    finally:
        db.close()
