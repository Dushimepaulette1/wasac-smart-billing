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
def test_when_a_v1_bill_is_calculated_should_match_its_tiers(m3, total):
    bill = billing.calculate_bill(m3, "v1-provisional")
    assert bill["total"] == pytest.approx(total) and bill["vat_amount"] == 0


@pytest.mark.parametrize("m3, without_vat, vat, total", [
    (0, 0, 0, 1000),
    (5, 1700, 310, 3010),
    (20, 12500, 2290, 15790),
    (50, 37850, 6929.05, 45779.05),
    (51, 38727, 7089.54, 46816.54),
])
def test_when_a_wasac_bill_is_calculated_should_charge_the_tiers_then_vat_then_the_service_charge(
    m3, without_vat, vat, total,
):
    bill = billing.calculate_bill(m3, "v2-wasac-residential")
    assert sum(bill[f"tier{n}_amount"] for n in range(1, 5)) == pytest.approx(without_vat)
    assert bill["vat_amount"] == pytest.approx(vat)
    assert bill["service_charge"] == 1000 and bill["total"] == pytest.approx(total)


def test_the_wasac_tariff_should_keep_the_published_rates():
    wasac = billing.tariff("v2-wasac-residential")
    assert wasac["tiers"] == [[5, 340], [15, 720], [30, 845], [None, 877]]
    assert wasac["tiers_vat_inclusive"] == [402, 852, 999.635, 1037.491]


def test_today_should_bill_new_readings_with_the_wasac_tariff():
    assert billing.tariff()["version"] == "v2-wasac-residential"
    assert billing.bill_columns(billing.calculate_bill(20)).keys().isdisjoint({"total", "vat_amount"})


def test_when_a_new_tariff_starts_should_use_it_for_new_bills_and_keep_old_bills_on_theirs(monkeypatch):
    new = {"version": "v2", "effective_from": "2026-01-01", "tiers": [[5, 400], [10, 600], [15, 800], [None, 1100]],
           "service_charge": 1200}
    monkeypatch.setattr(billing, "TARIFFS", billing.TARIFFS + [new])
    bill = billing.build_bill("C", 1, 5)
    assert bill.tariff_version == "v2" and bill.amount_due == 3200
    assert billing.calculate_bill(5, "v1-provisional")["total"] == 2750
    assert billing.bill_tariff(Bill())["version"] == "v1-provisional"  # no version: the original


def test_when_a_tariff_gives_no_vat_rates_should_add_no_vat(monkeypatch):
    plain = {"version": "v9", "effective_from": "2020-01-01", "tiers": [[5, 100], [None, 200]], "service_charge": 0}
    monkeypatch.setattr(billing, "TARIFFS", billing.TARIFFS + [plain])
    assert billing.calculate_bill(6, "v9")["vat_amount"] == 0 and billing.calculate_bill(6, "v9")["total"] == 700


def test_when_a_version_is_unknown_should_refuse_rather_than_guess():
    with pytest.raises(ValueError):
        billing.calculate_bill(5, "nope")


def test_when_estimating_should_show_the_rates_in_force(anon_client):
    body = anon_client.post("/calculate-bill", json={"consumption_m3": 20}).json()
    assert body["tariff_version"] == "v2-wasac-residential"
    assert [body["breakdown"][f"tier{n}"]["rate_rwf"] for n in range(1, 5)] == [340, 720, 845, 877]
    assert [body["breakdown"][f"tier{n}"]["rate_with_vat_rwf"] for n in range(1, 5)] == [402, 852, 999.635, 1037.491]
    assert body["vat_amount"] == 2290 and body["total_amount_due"] == 15790


def test_when_a_reading_is_billed_should_record_the_tariff_version(db):
    from app.db.init_db import LATE_COLUMNS
    assert ("bills", "tariff_version", "VARCHAR(40)") in LATE_COLUMNS
    bill = billing.build_bill("C", 1, 12)
    assert bill.tariff_version == "v2-wasac-residential"
    assert bill.amount_due == billing.calculate_bill(12, "v2-wasac-residential")["total"]


def test_when_an_old_bill_is_explained_should_use_its_version(anon_client):
    old = anon_client.post("/calculate-bill", json={"consumption_m3": 5, "tariff_version": "v1-provisional"}).json()
    assert old["total_amount_due"] == 2750 and old["vat_amount"] == 0
    assert anon_client.post("/calculate-bill", json={"consumption_m3": 5, "tariff_version": "nope"}).status_code == 422


def test_amounts_should_carry_no_float_noise():
    assert billing.calculate_bill(3.54, "v1-provisional")["total"] == 2239.0
    assert billing.calculate_bill(3.54, "v2-wasac-residential")["total"] == 2423.08
    assert billing.whole_francs(6460.5) == 6461 and billing.whole_francs(6460.49) == 6460 and billing.whole_francs(2.5) == 3


def test_when_an_old_bill_is_corrected_should_keep_its_own_rates_and_no_vat(db):
    from app.services.bill_corrections import _change
    old = Bill(bill_id=1, consumption_m3=5, tariff_version="v1-provisional")
    change = _change(db, old, 6, charges=2750)
    assert change.tariff_version == "v1-provisional" and change.amount_after == 3280 and change.tiers["vat_amount"] == 0
