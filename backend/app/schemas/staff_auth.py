"""Staff sign-in, accounts and the activity log (app/api/routes/staff_auth.py)."""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict


class LoginRequest(BaseModel):
    username: str
    password: str


class StaffUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    username: str
    full_name: str
    role: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: int
    user: StaffUserOut


class StaffActionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    at: datetime
    username: str
    action: str
    target: Optional[str] = None
    detail: Optional[str] = None


class StaffAccountOut(StaffUserOut):
    is_active: bool
    created_at: datetime
    last_sign_in: Optional[datetime] = None


class StaffAccountCreate(BaseModel):
    username: str
    full_name: str
    role: Literal["officer", "supervisor", "admin"] = "officer"


class StaffAccountUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[Literal["officer", "supervisor", "admin"]] = None
    is_active: Optional[bool] = None


class TemporaryPasswordResponse(BaseModel):
    """The new account's (or reset) password, shown once to the admin to pass on."""
    account: StaffAccountOut
    temporary_password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class SmsOutboxOut(BaseModel):
    """One message sent through the Africa's Talking sandbox (admins only)."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    at: datetime
    phone: str
    message: str
    status: str
