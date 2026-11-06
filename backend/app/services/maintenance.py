"""Remove expired photo content while the API is awake, independently of new uploads."""
import asyncio
import logging
import os

from app.db import session
from app.services.photo_evidence import purge

logger = logging.getLogger(__name__)


def cleanup_interval() -> int:
    """At most hourly by default; refuse a tight loop after a configuration mistake."""
    try:
        return max(60, int(os.getenv("PHOTO_CLEANUP_INTERVAL_SECONDS", "3600")))
    except ValueError:
        return 3600


def clean_expired_photos() -> None:
    """One transaction; callable from the API or an external scheduled task."""
    with session.SessionLocal() as db:
        purge(db)
        db.commit()


async def clean_photos_periodically() -> None:
    """Also runs on startup. A sleeping hosting instance needs an external scheduler."""
    while True:
        try:
            await asyncio.to_thread(clean_expired_photos)
        except Exception:
            # Do not log exception text: database errors can contain customer values.
            logger.error("Photo cleanup failed; check database availability and retry the cleanup command.")
        await asyncio.sleep(cleanup_interval())
