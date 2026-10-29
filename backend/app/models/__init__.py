"""Every database table, in one place: `from app.models import Customer, Bill`.

    household.py       customers, meters
    reading.py         readings, reading_evidence (where the photo was taken)
    bill.py            bills
    anomaly_flag.py    anomaly_flags, message_dismissals (messages a household deleted)
    staff.py           staff_users, staff_temporary_passwords, staff_actions (audit log)
    household_code.py  household_codes (SMS sign-in)
    sms_outbox.py      sms_outbox (sandbox SMS, for admins)
    payment.py         payments (MTN Mobile Money attempts)
    photo_read.py      photo_reads (the photo and what the reader saw, for reviewers)
    push_subscription.py  push_subscriptions (phones that turned alerts on)
"""
from app.models.anomaly_flag import FLAG_STATUS_OPEN, FLAG_STATUS_RESOLVED, AnomalyFlag, MessageDismissal
from app.models.bill import Bill
from app.models.household import Customer, Meter
from app.models.household_code import HouseholdCode
from app.models.payment import Payment
from app.models.photo_read import PhotoRead
from app.models.push_subscription import PushSubscription
from app.models.reading import Reading, ReadingEvidence
from app.models.sms_outbox import SmsOutbox
from app.models.staff import ROLES, StaffAction, StaffTemporaryPassword, StaffUser

__all__ = [
    "AnomalyFlag", "Bill", "MessageDismissal", "Customer", "FLAG_STATUS_OPEN", "FLAG_STATUS_RESOLVED", "HouseholdCode",
    "Meter", "Payment", "PhotoRead", "PushSubscription", "ROLES", "Reading", "ReadingEvidence", "SmsOutbox", "StaffAction",
    "StaffTemporaryPassword", "StaffUser",
]
