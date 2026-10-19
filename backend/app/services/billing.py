"""WASAC's tiered water tariff, and turning a confirmed reading into a bill.

    first 5 m3    350 RWF/m3
    next 10 m3    530 RWF/m3
    next 15 m3    791 RWF/m3
    above 30 m3  1000 RWF/m3
    + 1000 RWF service charge per bill
"""
from datetime import datetime

from app.models import Bill


def calculate_bill(consumption: float) -> dict:
    """WASAC tiered tariff calculation."""
    remaining = consumption
    t1 = min(remaining, 5)
    remaining -= t1
    t2 = min(remaining, 10)
    remaining -= t2
    t3 = min(remaining, 15)
    remaining -= t3
    t4 = max(remaining, 0)

    a1 = t1 * 350
    a2 = t2 * 530
    a3 = t3 * 791
    a4 = t4 * 1000
    service = 1000.0

    return {
        "tier1_units": t1, "tier2_units": t2, "tier3_units": t3, "tier4_units": t4,
        "tier1_amount": a1, "tier2_amount": a2, "tier3_amount": a3, "tier4_amount": a4,
        "service_charge": service,
        "total": a1 + a2 + a3 + a4 + service,
    }


def build_bill(customer_id: str, reading_id: int, consumption: float) -> Bill:
    data = calculate_bill(consumption)
    return Bill(
        customer_id=customer_id,
        reading_id=reading_id,
        consumption_m3=consumption,
        **{k: v for k, v in data.items() if k != "total"},
        amount_due=data["total"],
        payment_status="unpaid",
        created_at=datetime.utcnow(),
    )
