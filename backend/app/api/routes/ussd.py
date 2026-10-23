"""POST /ussd: the Africa's Talking USSD callback (menu in app/services/ussd_menu.py).

Africa's Talking does not sign its USSD callbacks, so the callback URL carries a secret:
    https://wasac-api.onrender.com/ussd?token=<USSD_CALLBACK_TOKEN>
Without USSD_CALLBACK_TOKEN set, or with a wrong token, the endpoint refuses (403): nobody can
send readings or start payments for someone else's phone number.
"""
import os
import secrets

from fastapi import APIRouter, Depends, Form, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.ussd_menu import handle

router = APIRouter()


@router.post("/ussd", response_class=PlainTextResponse)
async def ussd_callback(
    token: str = Query(default=""),
    session_id: str = Form(default="", alias="sessionId"),
    service_code: str = Form(default="", alias="serviceCode"),
    phone_number: str = Form(alias="phoneNumber"),
    text: str = Form(default=""),
    db: Session = Depends(get_db),
):
    expected = os.getenv("USSD_CALLBACK_TOKEN", "").strip()
    if not expected or not secrets.compare_digest(token, expected):
        raise HTTPException(status_code=403, detail="Unknown caller.")
    return await run_in_threadpool(handle, db, phone_number, text)
