"""WASAC's tiered water tariff, and turning a confirmed reading into a bill.

Volumes are kept to the litre (3 decimals) and money to 2 decimals, so float noise never reaches a
bill. Bills can carry part of a franc (litres are billed); payments are in whole francs (whole_francs).

Tariffs are versioned in app/services/tariffs.json: four tiers given as block sizes, and a service
charge per bill. A version may also give each tier's VAT-inclusive rate (tiers_vat_inclusive, as
WASAC publishes them); the bill then shows the water at the rates without VAT and the difference as
VAT. The service charge carries no VAT (the published tariff does not say it does). A bill records the version it was made with, so a later
correction recalculates it with its own rates. A version is never edited once bills use it; a new
tariff is a new entry, used for new bills from its effective_from date. Bills from before versions
existed have tariff_version NULL and used the first version (the rates never changed before that).
The rates are provisional until WASAC confirms the effective date and the service charge.
"""
import json
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Optional

from app.models import Bill

TARIFFS = json.loads((Path(__file__).with_name("tariffs.json")).read_text(encoding="utf-8"))
ORIGINAL_VERSION = TARIFFS[0]["version"]


def tariff(version: Optional[str] = None) -> dict:
    """A version by name (NULL on an old bill: the original); no name: the one in force today."""
    if version is None:
        today = datetime.utcnow().strftime("%Y-%m-%d")
        return [t for t in TARIFFS if t["effective_from"] <= today][-1]
    for t in TARIFFS:
        if t["version"] == version:
            return t
    raise ValueError(f"Unknown tariff version {version}")


def bill_tariff(bill: Bill) -> dict:
    return tariff(bill.tariff_version or ORIGINAL_VERSION)


def whole_francs(amount: float) -> int:
    """What can actually be collected: MoMo takes whole francs. Half a franc rounds up."""
    return int(Decimal(str(amount)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def calculate_bill(consumption: float, version: Optional[str] = None) -> dict:
    """WASAC tiered tariff calculation. Tier amounts are without VAT; vat_amount is the rest of the
    VAT-inclusive price (0 for a version that gives none)."""
    rates = tariff(version)
    with_vat = rates.get("tiers_vat_inclusive") or [rate for _, rate in rates["tiers"]]
    remaining = consumption
    data = {}
    total = 0.0
    vat = 0.0
    for n, ((size, rate), rate_with_vat) in enumerate(zip(rates["tiers"], with_vat), start=1):
        units = round(max(remaining, 0) if size is None else min(remaining, size), 3)
        remaining = round(remaining - units, 3)
        amount = round(units * rate, 2)
        data[f"tier{n}_units"], data[f"tier{n}_amount"] = units, amount
        total += amount
        vat += round(units * rate_with_vat, 2) - amount
    vat = round(vat, 2)
    service = float(rates["service_charge"])
    return {**data, "vat_amount": vat, "service_charge": service, "total": round(total + vat + service, 2)}


def bill_columns(data: dict) -> dict:
    """The parts of calculate_bill() that a Bill row stores (the total is its amount_due; VAT is
    worked out again from its tariff version)."""
    return {k: v for k, v in data.items() if k not in ("total", "vat_amount")}


def build_bill(customer_id: str, reading_id: int, consumption: float) -> Bill:
    rates = tariff()
    data = calculate_bill(consumption, rates["version"])
    return Bill(
        customer_id=customer_id,
        reading_id=reading_id,
        consumption_m3=consumption,
        **bill_columns(data),
        amount_due=data["total"],
        payment_status="unpaid",
        tariff_version=rates["version"],
        created_at=datetime.utcnow(),
    )
