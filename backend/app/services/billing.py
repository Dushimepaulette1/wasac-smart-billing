"""WASAC's tiered water tariff, and turning a confirmed reading into a bill.

Tariffs are versioned in app/services/tariffs.json: four tiers (first 5 m3, next 10, next 15, the
rest) and a service charge per bill. A bill records the version it was made with, so a later
correction recalculates it with its own rates. A version is never edited once bills use it; a new
tariff is a new entry, used for new bills from its effective_from date. Bills from before versions
existed have tariff_version NULL and used the first version (the rates never changed before that).
The rates are provisional until confirmed against the RURA/WASAC tariff.
"""
import json
from datetime import datetime
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


def calculate_bill(consumption: float, version: Optional[str] = None) -> dict:
    """WASAC tiered tariff calculation."""
    rates = tariff(version)
    remaining = consumption
    data = {}
    total = 0.0
    for n, (size, rate) in enumerate(rates["tiers"], start=1):
        units = max(remaining, 0) if size is None else min(remaining, size)
        remaining -= units
        amount = units * rate
        data[f"tier{n}_units"], data[f"tier{n}_amount"] = units, amount
        total += amount
    service = float(rates["service_charge"])
    return {**data, "service_charge": service, "total": total + service}


def build_bill(customer_id: str, reading_id: int, consumption: float) -> Bill:
    rates = tariff()
    data = calculate_bill(consumption, rates["version"])
    return Bill(
        customer_id=customer_id,
        reading_id=reading_id,
        consumption_m3=consumption,
        **{k: v for k, v in data.items() if k != "total"},
        amount_due=data["total"],
        payment_status="unpaid",
        tariff_version=rates["version"],
        created_at=datetime.utcnow(),
    )
