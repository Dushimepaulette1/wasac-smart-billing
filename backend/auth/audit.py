"""Write and read the staff audit log (auth.models.StaffAction)."""
from typing import Optional

from fastapi import Request
from sqlalchemy.orm import Session

from auth.models import StaffAction
from ratelimit import client_ip


def record(
    db: Session,
    username: str,
    action: str,
    *,
    target: Optional[str] = None,
    detail: Optional[str] = None,
    request: Optional[Request] = None,
    commit: bool = True,
) -> StaffAction:
    """Add one audit row. Values are cut to the column sizes, so a long typed
    username on a failed sign-in cannot break the insert."""
    row = StaffAction(
        username=(username or "?")[:64],
        action=action[:32],
        target=target[:64] if target else None,
        detail=detail[:200] if detail else None,
        ip=client_ip(request)[:64] if request is not None else None,
    )
    db.add(row)
    if commit:
        db.commit()
    return row
