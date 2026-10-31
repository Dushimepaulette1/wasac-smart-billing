"""The ways a bill can be paid. app/services/payments.py runs one attempt the same way for all of
them (one open attempt per bill, one receipt, an audit trail); what differs lives here.

    MomoApiProvider    MTN Mobile Money API: MTN sends a PIN prompt, and MTN's status settles it
    MomoPayProvider    USSD to WASAC's merchant code: an officer settles it from the transaction ID
    SimulatedProvider  tests and demos (PAYMENTS_SIMULATE=1): succeeds at once
"""
import os
from abc import ABC, abstractmethod
from typing import Optional

from app.models import Bill
from app.models.payment import MOMO_PAY, Payment
from app.services import momo

SIMULATED = "simulated"
API_PROVIDERS = ("momo", "momo_sandbox")


class PaymentProvider(ABC):
    """One way to collect money. `settles_at_once`: the attempt succeeds as soon as it exists.
    `asks_mtn`: only MTN's status can settle it, so earlier attempts are asked about first."""

    settles_at_once = False
    asks_mtn = False
    currency = "RWF"

    @property
    @abstractmethod
    def name(self) -> str:
        """Stored in payments.provider."""

    def start(self, payment: Payment, bill: Bill, phone: str) -> None:
        """Ask for the money, after the attempt is committed. May raise momo.MomoError."""

    def receipt_id(self, payment: Payment, bill: Bill) -> Optional[str]:
        """The transaction ID of an attempt that settles at once."""
        return None


class MomoApiProvider(PaymentProvider):
    asks_mtn = True

    def __init__(self):
        self.currency = momo.currency()

    @property
    def name(self) -> str:
        return momo.provider_name()

    def start(self, payment: Payment, bill: Bill, phone: str) -> None:
        momo.request_to_pay(payment.reference_id, payment.amount, phone, external_id=f"bill-{bill.bill_id}",
                            note=f"WASAC water bill {bill.bill_id}")


class MomoPayProvider(PaymentProvider):
    name = MOMO_PAY


class SimulatedProvider(PaymentProvider):
    name = SIMULATED
    settles_at_once = True

    def receipt_id(self, payment: Payment, bill: Bill) -> Optional[str]:
        return f"SIM-{bill.bill_id:06d}-{payment.id}"


def choose_provider() -> PaymentProvider:
    """The MoMo API when its keys are set; otherwise MoMo Pay, or the simulation if switched on."""
    if momo.momo_configured():
        return MomoApiProvider()
    return SimulatedProvider() if os.getenv("PAYMENTS_SIMULATE", "0") == "1" else MomoPayProvider()
