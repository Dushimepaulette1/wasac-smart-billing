"""Tariff versions (app/services/tariffs.json): a bill keeps the rates it was made with."""
import pytest

from app.models import Bill
from app.services import billing


def test_the_original_version_should_keep_its_rates_for_ever():
    # Bills with no version rely on this entry. Add a new version; never change this one.
    first = billing.TARIFFS[0]
    assert first["version"] == billing.ORIGINAL_VERSION == "v1-provisional"
    assert first["tiers"] == [[5, 350], [10, 530], [15, 791], [None, 1000]] and first["service_charge"] == 1000


@pytest.mark.parametrize("m3, total", [
    (0, 1000), (5, 2750), (5.5, 3015), (15, 8050), (15.5, 8445.5), (30, 19915), (31, 20915), (31.46, 21375),
])
def test_when_a_bill_is_calculated_should_match_the_tiers(m3, total):
    assert billing.calculate_bill(m3)["total"] == pytest.approx(total)


def test_when_a_new_tariff_starts_should_use_it_for_new_bills_and_keep_old_bills_on_theirs(monkeypatch):
    new = {"version": "v2", "effective_from": "2026-01-01", "tiers": [[5, 400], [10, 600], [15, 800], [None, 1100]],
           "service_charge": 1200}
    monkeypatch.setattr(billing, "TARIFFS", billing.TARIFFS + [new])
    bill = billing.build_bill("C", 1, 5)
    assert bill.tariff_version == "v2" and bill.amount_due == 3200
    assert billing.calculate_bill(5, "v1-provisional")["total"] == 2750
    assert billing.bill_tariff(Bill())["version"] == "v1-provisional"  # no version: the original


def test_when_a_version_is_unknown_should_refuse_rather_than_guess():
    with pytest.raises(ValueError):
        billing.calculate_bill(5, "nope")


def test_when_estimating_should_show_the_rates_in_force(anon_client):
    body = anon_client.post("/calculate-bill", json={"consumption_m3": 20}).json()
    assert [body["breakdown"][f"tier{n}"]["rate_rwf"] for n in range(1, 5)] == [350, 530, 791, 1000]
    assert body["total_amount_due"] == billing.calculate_bill(20)["total"]


def test_when_a_reading_is_billed_should_record_the_tariff_version(db):
    from app.db.init_db import LATE_COLUMNS
    assert ("bills", "tariff_version", "VARCHAR(40)") in LATE_COLUMNS
    assert billing.build_bill("C", 1, 12).tariff_version == "v1-provisional"
