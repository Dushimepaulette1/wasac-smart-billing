"""MTN Mobile Money Collections: ask a household to pay ("Request to Pay") and check the answer.

    MOMO_SUBSCRIPTION_KEY   the Collections product's primary key (momodeveloper.mtn.com profile)
    MOMO_API_USER           the API user (a UUID) and its key; for the sandbox,
    MOMO_API_KEY            scripts/momo_sandbox_setup.py creates them
    MOMO_TARGET_ENVIRONMENT "sandbox" (default) or the live environment name MTN gives
    MOMO_BASE_URL           default https://sandbox.momodeveloper.mtn.com
    MOMO_CURRENCY           default EUR in the sandbox (the only currency it accepts), RWF live

Without the first three, payments are simulated (app/services/payments.py). Keys and full numbers
are never logged.
"""
import logging
import os
import time
from dataclasses import dataclass
from typing import Optional

import httpx

logger = logging.getLogger(__name__)
TIMEOUT_SECONDS = 15
_token: dict = {"value": None, "expires": 0.0}


class MomoError(Exception):
    """A safe message (no keys, no full numbers) for logs and the payment record.

    uncertain: the request may have reached MTN (a timeout after sending, a 5xx), so MTN may still
    send the payer a prompt. The attempt must stay open until MTN's status says how it ended."""

    def __init__(self, message: str, uncertain: bool = False):
        super().__init__(message)
        self.uncertain = uncertain


@dataclass
class MomoStatus:
    status: str                       # PENDING, SUCCESSFUL, FAILED, REJECTED, TIMEOUT, ..., NOT_FOUND
    transaction_id: Optional[str] = None
    reason: Optional[str] = None


def _settings():
    return (os.getenv("MOMO_SUBSCRIPTION_KEY", "").strip(), os.getenv("MOMO_API_USER", "").strip(),
            os.getenv("MOMO_API_KEY", "").strip())


def momo_configured() -> bool:
    return all(_settings())


def environment() -> str:
    return os.getenv("MOMO_TARGET_ENVIRONMENT", "sandbox").strip() or "sandbox"


def base_url() -> str:
    return (os.getenv("MOMO_BASE_URL", "https://sandbox.momodeveloper.mtn.com").strip()).rstrip("/")


def currency() -> str:
    return (os.getenv("MOMO_CURRENCY") or ("EUR" if environment() == "sandbox" else "RWF")).strip().upper()


def provider_name() -> str:
    return "momo_sandbox" if environment() == "sandbox" else "momo"


def msisdn(phone: str) -> str:
    """+250788123456 -> 250788123456 (MTN wants digits only, with the country code)."""
    return "".join(ch for ch in phone if ch.isdigit())


def reset_token() -> None:
    """For tests."""
    _token.update(value=None, expires=0.0)


def _access_token() -> str:
    if _token["value"] and time.time() < _token["expires"] - 60:
        return _token["value"]
    sub, user, key = _settings()
    try:
        r = httpx.post(f"{base_url()}/collection/token/", auth=(user, key),
                       headers={"Ocp-Apim-Subscription-Key": sub}, timeout=TIMEOUT_SECONDS)
    except httpx.HTTPError as e:
        raise MomoError(f"MTN MoMo could not be reached ({type(e).__name__})")
    if r.status_code != 200:
        raise MomoError(f"MTN MoMo refused the sign-in (HTTP {r.status_code}); check the MoMo keys")
    data = r.json()
    _token.update(value=data["access_token"], expires=time.time() + float(data.get("expires_in", 3600)))
    return _token["value"]


def _headers(reference_id: Optional[str] = None) -> dict:
    sub, _, _ = _settings()
    h = {"Authorization": f"Bearer {_access_token()}", "X-Target-Environment": environment(),
         "Ocp-Apim-Subscription-Key": sub}
    if reference_id:
        h["X-Reference-Id"] = reference_id
    return h


def request_to_pay(reference_id: str, amount: float, phone: str, external_id: str, note: str) -> None:
    """Ask MTN to send the payer a PIN prompt. MTN answers 202 at once; the result comes later."""
    body = {
        "amount": str(int(round(amount))),
        "currency": currency(),
        "externalId": external_id,
        "payer": {"partyIdType": "MSISDN", "partyId": msisdn(phone)},
        "payerMessage": note[:160],
        "payeeNote": note[:160],
    }
    headers = _headers(reference_id)  # a token failure here means nothing was sent
    try:
        r = httpx.post(f"{base_url()}/collection/v1_0/requesttopay", json=body,
                       headers=headers, timeout=TIMEOUT_SECONDS)
    except (httpx.ConnectError, httpx.ConnectTimeout) as e:  # no connection: the request never left
        raise MomoError(f"MTN MoMo could not be reached ({type(e).__name__})")
    except httpx.HTTPError as e:  # sent, but no answer: MTN may have it
        raise MomoError(f"No answer from MTN MoMo ({type(e).__name__})", uncertain=True)
    if r.status_code >= 500:
        raise MomoError(f"MTN MoMo had an error (HTTP {r.status_code})", uncertain=True)
    if r.status_code != 202:
        raise MomoError(f"MTN MoMo did not accept the request (HTTP {r.status_code})")
    logger.info("[MoMo] request to pay sent: ref=%s amount=%s %s", reference_id, body["amount"], body["currency"])


def payment_status(reference_id: str) -> MomoStatus:
    """MTN's answer for one request to pay. NOT_FOUND: MTN has no request with this reference id,
    so no prompt was ever sent for it."""
    try:
        r = httpx.get(f"{base_url()}/collection/v1_0/requesttopay/{reference_id}",
                      headers=_headers(), timeout=TIMEOUT_SECONDS)
    except httpx.HTTPError as e:
        raise MomoError(f"MTN MoMo could not be reached ({type(e).__name__})")
    if r.status_code == 404:
        return MomoStatus(status="NOT_FOUND")
    if r.status_code != 200:
        raise MomoError(f"MTN MoMo did not answer the status check (HTTP {r.status_code})")
    data = r.json()
    reason = data.get("reason")
    if isinstance(reason, dict):
        reason = reason.get("message") or reason.get("code")
    return MomoStatus(status=str(data.get("status", "PENDING")).upper(),
                      transaction_id=data.get("financialTransactionId"), reason=reason)
