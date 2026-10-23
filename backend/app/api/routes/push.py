"""Phone alerts (web push) for signed-in households (app/services/push.py).

    GET  /household/push/key          the public key the browser subscribes with (null: alerts off)
    POST /household/push/subscribe    this browser's subscription, for the signed-in phone
    POST /household/push/unsubscribe  stop alerts to this browser
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import Access, household_access
from app.db.session import get_db
from app.services import push

router = APIRouter(prefix="/household/push")


class PushKeys(BaseModel):
    p256dh: str = Field(min_length=10, max_length=200)
    auth: str = Field(min_length=8, max_length=100)


class SubscribeRequest(BaseModel):
    """A browser's PushSubscription.toJSON()."""
    endpoint: str = Field(min_length=10, max_length=1024, pattern=r"^https://")
    keys: PushKeys


class UnsubscribeRequest(BaseModel):
    endpoint: str = Field(min_length=10, max_length=1024)


def _household(access: Access) -> str:
    if access.staff is not None or not access.phone:
        raise HTTPException(status_code=400, detail="Alerts are for households.")
    return access.phone


@router.get("/key")
async def push_key():
    """200 either way, so a phone asking before alerts are set up logs no error."""
    return {"public_key": push.public_key()}


@router.post("/subscribe", status_code=204)
async def push_subscribe(body: SubscribeRequest, db: Session = Depends(get_db), access: Access = Depends(household_access)):
    if not push.configured():
        raise HTTPException(status_code=404, detail="Alerts are not set up.")
    push.subscribe(db, _household(access), body.endpoint, body.keys.p256dh, body.keys.auth)


@router.post("/unsubscribe", status_code=204)
async def push_unsubscribe(body: UnsubscribeRequest, db: Session = Depends(get_db), access: Access = Depends(household_access)):
    push.unsubscribe(db, _household(access), body.endpoint)
