"""POST /auth/login, GET /auth/me, and the require_staff dependency."""
import time
from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from auth.models import StaffUser
from auth.security import make_token, read_token, verify_password
from database import get_db
from schemas import LoginRequest, LoginResponse, StaffUserOut

router = APIRouter(prefix="/auth")

WRONG_LOGIN = "Wrong username or password."
MAX_FAILURES = 5
LOCK_SECONDS = 5 * 60

# Failed sign-ins per username: (count, time of first failure in the window).
# In memory, per process: enough to slow guessing on a single server.
_failures: dict[str, tuple[int, float]] = defaultdict(lambda: (0, 0.0))


def _locked(username: str, now: float) -> bool:
    count, since = _failures[username]
    if count and now - since > LOCK_SECONDS:
        _failures.pop(username, None)
        return False
    return count >= MAX_FAILURES


def _record_failure(username: str, now: float) -> None:
    count, since = _failures[username]
    _failures[username] = (count + 1, since if count else now)


def reset_failures() -> None:
    """For tests."""
    _failures.clear()


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, db: Session = Depends(get_db)):
    username = body.username.strip().lower()
    now = time.time()
    if _locked(username, now):
        raise HTTPException(
            status_code=429,
            detail="Too many wrong attempts. Wait 5 minutes, then try again.",
        )
    user = db.query(StaffUser).filter(StaffUser.username == username).first()
    if not user or not user.is_active or not verify_password(body.password, user.password_hash):
        _record_failure(username, now)
        raise HTTPException(status_code=401, detail=WRONG_LOGIN)
    _failures.pop(username, None)
    token, expires_at = make_token(user.username, now=now)
    return LoginResponse(access_token=token, expires_at=expires_at, user=StaffUserOut.model_validate(user))


def require_staff(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> StaffUser:
    """Dependency for staff-only routes: a valid Bearer token for an active user."""
    scheme, _, token = (authorization or "").partition(" ")
    username = read_token(token) if scheme.lower() == "bearer" and token else None
    user = db.query(StaffUser).filter(StaffUser.username == username).first() if username else None
    if not user or not user.is_active:
        raise HTTPException(
            status_code=401,
            detail="Sign in to continue.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


@router.get("/me", response_model=StaffUserOut)
async def me(user: StaffUser = Depends(require_staff)):
    return user
