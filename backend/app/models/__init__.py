"""Every database table, in one place: `from app.models import Customer, Bill`.

    household.py       customers, meters
    reading.py         readings, reading_evidence (where the photo was taken)
    bill.py            bills
    anomaly_flag.py    anomaly_flags
    staff.py           staff_users, staff_actions (audit log)
    household_code.py  household_codes (SMS sign-in)
    sms_outbox.py      sms_outbox (sandbox SMS, for admins)
    payment.py         payments (MTN Mobile Money attempts)
"""
from app.models.anomaly_flag import FLAG_STATUS_OPEN, FLAG_STATUS_RESOLVED, AnomalyFlag
from app.models.bill import Bill
from app.models.household import Customer, Meter
from app.models.household_code import HouseholdCode
from app.models.payment import Payment
from app.models.reading import Reading, ReadingEvidence
from app.models.sms_outbox import SmsOutbox
from app.models.staff import ROLES, StaffAction, StaffUser

__all__ = [
    "AnomalyFlag", "Bill", "Customer", "FLAG_STATUS_OPEN", "FLAG_STATUS_RESOLVED", "HouseholdCode",
    "Meter", "Payment", "ROLES", "Reading", "ReadingEvidence", "SmsOutbox", "StaffAction", "StaffUser",
]
