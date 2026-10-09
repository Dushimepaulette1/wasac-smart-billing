"""Values stored in readings.validation_status, and which anomaly types hold a reading for review."""
from anomaly.rules import AnomalyType

READING_VALID = "valid"
READING_FLAGGED = "anomaly_flagged"  # confirmed and billed, but staff should look at it
READING_PENDING = "pending_review"   # not confirmed: not billed, not used as history
READING_REJECTED = "rejected"        # discarded by staff: never billed, never used as history

NOT_CONFIRMED = (READING_PENDING, READING_REJECTED)

PENDING_REVIEW_TYPES = {AnomalyType.MISREAD_SUSPECTED, AnomalyType.SPIKE}
