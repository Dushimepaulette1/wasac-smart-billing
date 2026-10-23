"""Staff sign-in, roles, the audit log and staff accounts.

    POST  /auth/login                          sign in (every attempt is logged)
    GET   /auth/me                             the signed-in person
    POST  /auth/password                       change your own password (a new token: old sessions end)
    GET   /auth/activity                       audit log (officers: their own rows)
    GET   /auth/staff                          accounts                      admin
    POST  /auth/staff                          new account, temporary password  admin
    PATCH /auth/staff/{username}               name, role, active             admin
    POST  /auth/staff/{username}/reset-password  new temporary password       admin
                                                 (ends that person's sessions)

A temporary password only lets its owner see /auth/me and change it (require_staff refuses the rest).
    GET   /auth/sms-outbox                     SMS sent through the sandbox   admin
"""
import re
import secrets
import time
from collections import defaultdict
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import has_temporary_password, require_role, require_signed_in, require_staff, role_at_least
from app.core.security import hash_password, make_staff_token, verify_password
from app.db.session import get_db
from app.models import SmsOutbox, StaffAction, StaffTemporaryPassword, StaffUser
from app.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    StaffAccountCreate,
    StaffAccountOut,
    StaffAccountUpdate,
    SmsOutboxOut,
    StaffActionOut,
    StaffUserOut,
    TemporaryPasswordResponse,
)
from app.services.audit import record

router = APIRouter(prefix="/auth")

WRONG_LOGIN = "Wrong username or password."
MAX_FAILURES = 5
LOCK_SECONDS = 5 * 60
MIN_PASSWORD_LENGTH = 10
USERNAME_PATTERN = re.compile(r"^[a-z0-9._-]{3,32}$")
# No 0/O, 1/l/I: the temporary password is read out or copied by hand.
_PASSWORD_ALPHABET = "abcdefghijkmnpqrstuvwxyz23456789"

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


def _user_out(db: Session, user: StaffUser) -> StaffUserOut:
    return StaffUserOut.model_validate(user).model_copy(
        update={"must_change_password": has_temporary_password(db, user)}
    )


def _session(db: Session, user: StaffUser, now: Optional[float] = None) -> LoginResponse:
    token, expires_at = make_staff_token(user.username, user.password_hash, now=now)
    return LoginResponse(access_token=token, expires_at=expires_at, user=_user_out(db, user))


def _set_temporary_password(db: Session, user: StaffUser) -> str:
    password = temporary_password()
    user.password_hash = hash_password(password)
    db.flush()  # a new account needs its id
    if not has_temporary_password(db, user):
        db.add(StaffTemporaryPassword(user_id=user.id))
    return password


def temporary_password() -> str:
    """Three groups of four, e.g. 'k7mq-x3vd-9tpa' (about 77 bits)."""
    return "-".join("".join(secrets.choice(_PASSWORD_ALPHABET) for _ in range(4)) for _ in range(3))


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    username = body.username.strip().lower()
    now = time.time()
    if _locked(username, now):
        record(db, username, "sign_in_failed", detail="locked", request=request)
        raise HTTPException(
            status_code=429,
            detail="Too many wrong attempts. Wait 5 minutes, then try again.",
        )
    user = db.query(StaffUser).filter(StaffUser.username == username).first()
    if not user or not user.is_active or not verify_password(body.password, user.password_hash):
        _record_failure(username, now)
        record(db, username, "sign_in_failed", request=request)
        raise HTTPException(status_code=401, detail=WRONG_LOGIN)
    _failures.pop(username, None)
    record(db, user.username, "sign_in", request=request)
    return _session(db, user, now=now)


@router.get("/me", response_model=StaffUserOut)
async def me(db: Session = Depends(get_db), user: StaffUser = Depends(require_signed_in)):
    return _user_out(db, user)


@router.post("/password", response_model=LoginResponse)
async def change_password(
    body: ChangePasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: StaffUser = Depends(require_signed_in),
):
    """Every other session of this account ends; this one continues with the new token returned."""
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Your current password is not right.")
    if len(body.new_password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(status_code=400, detail=f"Use at least {MIN_PASSWORD_LENGTH} characters.")
    if body.new_password == body.current_password:
        raise HTTPException(status_code=400, detail="Choose a password different from the current one.")
    user.password_hash = hash_password(body.new_password)
    db.query(StaffTemporaryPassword).filter(StaffTemporaryPassword.user_id == user.id).delete()
    record(db, user.username, "password_changed", request=request, commit=False)
    db.commit()
    return _session(db, user)


@router.get("/activity", response_model=List[StaffActionOut])
async def activity(
    limit: int = Query(100, ge=1, le=500),
    username: Optional[str] = None,
    action: Optional[str] = None,
    db: Session = Depends(get_db),
    user: StaffUser = Depends(require_staff),
):
    """Newest first. Officers see only their own rows; supervisors and admins see everyone's."""
    query = db.query(StaffAction)
    if not role_at_least(user, "supervisor"):
        query = query.filter(StaffAction.username == user.username)
    elif username:
        query = query.filter(StaffAction.username == username.strip().lower())
    if action:
        query = query.filter(StaffAction.action == action)
    return query.order_by(StaffAction.at.desc(), StaffAction.id.desc()).limit(limit).all()


def _account(db: Session, user: StaffUser) -> StaffAccountOut:
    last = (
        db.query(func.max(StaffAction.at))
        .filter(StaffAction.username == user.username, StaffAction.action == "sign_in")
        .scalar()
    )
    return StaffAccountOut(
        username=user.username, full_name=user.full_name, role=user.role,
        is_active=user.is_active, created_at=user.created_at, last_sign_in=last,
    )


def _find(db: Session, username: str) -> StaffUser:
    user = db.query(StaffUser).filter(StaffUser.username == username.strip().lower()).first()
    if not user:
        raise HTTPException(status_code=404, detail="No staff account with that username.")
    return user


@router.get("/staff", response_model=List[StaffAccountOut])
async def list_accounts(db: Session = Depends(get_db), _admin: StaffUser = Depends(require_role("admin"))):
    users = db.query(StaffUser).order_by(StaffUser.is_active.desc(), StaffUser.full_name).all()
    return [_account(db, u) for u in users]


@router.post("/staff", response_model=TemporaryPasswordResponse, status_code=201)
async def create_account(
    body: StaffAccountCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin: StaffUser = Depends(require_role("admin")),
):
    username = body.username.strip().lower()
    full_name = body.full_name.strip()
    if not USERNAME_PATTERN.match(username):
        raise HTTPException(status_code=400, detail="Usernames are 3 to 32 lowercase letters, digits, dots, dashes or underscores.")
    if not full_name:
        raise HTTPException(status_code=400, detail="Enter the person's full name.")
    if db.query(StaffUser).filter(StaffUser.username == username).first():
        raise HTTPException(status_code=409, detail="That username is taken.")
    user = StaffUser(username=username, full_name=full_name[:120], role=body.role, password_hash="")
    db.add(user)
    password = _set_temporary_password(db, user)
    record(db, admin.username, "account_created", target=username, detail=body.role, request=request, commit=False)
    db.commit()
    return TemporaryPasswordResponse(account=_account(db, user), temporary_password=password)


@router.patch("/staff/{username}", response_model=StaffAccountOut)
async def update_account(
    username: str,
    body: StaffAccountUpdate,
    request: Request,
    db: Session = Depends(get_db),
    admin: StaffUser = Depends(require_role("admin")),
):
    user = _find(db, username)
    if user.id == admin.id and (body.is_active is False or (body.role and body.role != user.role)):
        raise HTTPException(status_code=400, detail="You cannot disable your own account or change your own role.")
    changes = []
    if body.full_name is not None and body.full_name.strip() and body.full_name.strip() != user.full_name:
        user.full_name = body.full_name.strip()[:120]
        changes.append("name")
    if body.role is not None and body.role != user.role:
        changes.append(f"role {user.role}->{body.role}")
        user.role = body.role
    if body.is_active is not None and body.is_active != user.is_active:
        user.is_active = body.is_active
        changes.append("enabled" if body.is_active else "disabled")
    if changes:
        record(db, admin.username, "account_updated", target=user.username, detail=", ".join(changes),
               request=request, commit=False)
        db.commit()
    return _account(db, user)


@router.post("/staff/{username}/reset-password", response_model=TemporaryPasswordResponse)
async def reset_password(
    username: str,
    request: Request,
    db: Session = Depends(get_db),
    admin: StaffUser = Depends(require_role("admin")),
):
    user = _find(db, username)
    password = _set_temporary_password(db, user)
    _failures.pop(user.username, None)
    record(db, admin.username, "password_reset", target=user.username, request=request, commit=False)
    db.commit()
    return TemporaryPasswordResponse(account=_account(db, user), temporary_password=password)


@router.get("/sms-outbox", response_model=List[SmsOutboxOut])
async def sms_outbox(
    limit: int = Query(100, ge=1, le=200),
    db: Session = Depends(get_db),
    _admin: StaffUser = Depends(require_role("admin")),
):
    """Newest first. Only sandbox messages are kept (app/services/sms.py); they include sign-in codes."""
    return db.query(SmsOutbox).order_by(SmsOutbox.id.desc()).limit(limit).all()
