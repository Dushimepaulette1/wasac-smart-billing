"""Phone alerts (web push): "your reading was accepted", even with the app closed.

The household turns alerts on in the app (frontend/src/pwa/PushOptIn.tsx); the browser gives a
subscription, stored per phone number (app/models/push_subscription.py). When an officer decides
a reading (app/anomaly/review.py), every subscription for that household's phone gets a short
message; the service worker (frontend/public/sw.js) shows it and opens the app on tap.

Keys (VAPID): VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY, made once with scripts/make_vapid_keys.py;
VAPID_SUBJECT is a contact address for the push services (default mailto:support@mubazi.rw).
Without the keys, alerts are off and the app hides the switch. A subscription the browser has
dropped (404/410) is deleted. Endpoints and keys are never logged.
"""
import json
import logging
import os
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models import PushSubscription

logger = logging.getLogger(__name__)

PUSH_TIMEOUT_SECONDS = 5


def public_key() -> Optional[str]:
    key = os.getenv("VAPID_PUBLIC_KEY", "").strip()
    return key if key and os.getenv("VAPID_PRIVATE_KEY", "").strip() else None


def configured() -> bool:
    return public_key() is not None


def subscribe(db: Session, phone: str, endpoint: str, p256dh: str, auth: str) -> None:
    """Save (or move to this phone) one browser's subscription. Commits."""
    row = db.query(PushSubscription).filter(PushSubscription.endpoint == endpoint).first()
    if row is None:
        row = PushSubscription(endpoint=endpoint)
        db.add(row)
    row.phone, row.p256dh, row.auth = phone, p256dh, auth
    db.commit()


def unsubscribe(db: Session, phone: str, endpoint: str) -> None:
    db.query(PushSubscription).filter(PushSubscription.phone == phone, PushSubscription.endpoint == endpoint).delete()
    db.commit()


def send_to_phone(db: Session, phone: Optional[str], title: str, body: str, url: str = "/messages") -> int:
    """Send one alert to every browser subscribed for this phone. Returns how many took it.
    Never raises: an alert must not break the decision that caused it. Commits."""
    if not phone or not configured():
        return 0
    from pywebpush import WebPushException, webpush  # only loaded when alerts are on

    payload = json.dumps({"title": title, "body": body, "url": url, "tag": "mubazi-decision"})
    claims = {"sub": os.getenv("VAPID_SUBJECT", "mailto:support@mubazi.rw")}
    sent = 0
    for row in db.query(PushSubscription).filter(PushSubscription.phone == phone).all():
        try:
            webpush(
                {"endpoint": row.endpoint, "keys": {"p256dh": row.p256dh, "auth": row.auth}},
                payload,
                vapid_private_key=os.environ["VAPID_PRIVATE_KEY"].strip(),
                vapid_claims=dict(claims),
                timeout=PUSH_TIMEOUT_SECONDS,
                ttl=24 * 3600,
            )
            row.last_sent_at = datetime.utcnow()
            sent += 1
        except WebPushException as e:
            status = getattr(e.response, "status_code", None)
            if status in (404, 410):  # the browser dropped this subscription
                db.delete(row)
            logger.warning("Push alert failed (status %s)", status)
        except Exception as e:  # network, bad key: report the kind only
            logger.warning("Push alert failed (%s)", type(e).__name__)
    db.commit()
    return sent
