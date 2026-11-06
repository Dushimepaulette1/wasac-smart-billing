"""Delete expired photo content. Run daily from a scheduler, even when the web service sleeps."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.maintenance import clean_expired_photos  # noqa: E402


if __name__ == "__main__":
    clean_expired_photos()
    print("Expired photo cleanup completed.")
