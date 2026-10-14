"""Password hashing and signed session tokens, standard library only.

Passwords: PBKDF2-HMAC-SHA256 with a random salt, stored as
"pbkdf2_sha256$<iterations>$<salt>$<hash>".

Tokens: base64url(JSON payload) + "." + base64url(HMAC-SHA256 signature),
signed with WASAC_AUTH_SECRET. Without that variable a random secret is
made at start-up, so tokens stop working when the server restarts; set it
in production.
"""
import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from typing import Optional

PBKDF2_ITERATIONS = 600_000
TOKEN_TTL_SECONDS = 8 * 60 * 60  # one working day

_log = logging.getLogger(__name__)
_SECRET = os.getenv("WASAC_AUTH_SECRET", "").encode()
if not _SECRET:
    _SECRET = secrets.token_bytes(32)
    _log.warning("WASAC_AUTH_SECRET is not set: using a random secret; staff must sign in again after a restart.")


def hash_password(password: str, *, iterations: int = PBKDF2_ITERATIONS) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"pbkdf2_sha256${iterations}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, iterations, salt, expected = stored.split("$")
        if scheme != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), _unb64(salt), int(iterations))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest, _unb64(expected))


def make_token(username: str, *, now: Optional[float] = None, ttl: int = TOKEN_TTL_SECONDS) -> tuple[str, int]:
    """Return (token, expires_at as Unix seconds)."""
    expires_at = int((now if now is not None else time.time()) + ttl)
    payload = _b64(json.dumps({"sub": username, "exp": expires_at}, separators=(",", ":")).encode())
    return f"{payload}.{_sign(payload)}", expires_at


def read_token(token: str, *, now: Optional[float] = None) -> Optional[str]:
    """The username in a valid, unexpired token, or None."""
    try:
        payload, signature = token.split(".")
    except ValueError:
        return None
    if not hmac.compare_digest(signature, _sign(payload)):
        return None
    try:
        data = json.loads(_unb64(payload))
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict) or data.get("exp", 0) < (now if now is not None else time.time()):
        return None
    sub = data.get("sub")
    return sub if isinstance(sub, str) else None


def hash_code(phone: str, code: str) -> str:
    """One-time sign-in codes are stored only as this keyed hash, never in plain text."""
    return _b64(hmac.new(_SECRET, f"code:{phone}:{code}".encode(), hashlib.sha256).digest())


def _sign(payload: str) -> str:
    return _b64(hmac.new(_SECRET, payload.encode(), hashlib.sha256).digest())


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
