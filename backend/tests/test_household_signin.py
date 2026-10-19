"""Household sign-in with a one-time code, and households seeing only their own account."""
import pytest

from conftest import add_household, household_token, make_history

from app.utils.phone import normalize_phone
from app.models import HouseholdCode

PHONE = "+250788000111"  # add_household's default


@pytest.mark.parametrize("raw", ["0788000111", "788000111", "+250 788 000 111", "250-788-000-111", "(078) 800-0111"])
def test_phone_numbers_are_normalized(raw):
    assert normalize_phone(raw) == PHONE


@pytest.mark.parametrize("raw", ["", "12345", "0588000111", "+254712345678", "07880001110", "abc"])
def test_non_rwandan_mobiles_are_refused(raw):
    assert normalize_phone(raw) is None


def demo_household(db, meter_id="DEMO-MTR-001", phone="+250700000001"):
    return add_household(db, meter_id, make_history([0.4] * 3), phone=phone)


def test_demo_household_signs_in_with_the_code_shown(db, anon_client):
    customer_id = demo_household(db)
    sent = anon_client.post("/household/request-code", json={"phone": "0700 000 001"}).json()
    assert sent["phone"] == "+250700000001" and len(sent["demo_code"]) == 6
    stored = db.query(HouseholdCode).one()
    assert sent["demo_code"] not in stored.code_hash  # only a keyed hash is kept

    session = anon_client.post("/household/verify", json={"phone": "0700000001", "code": sent["demo_code"]}).json()
    assert [a["customer_id"] for a in session["accounts"]] == [customer_id]
    assert session["accounts"][0]["is_demo"] is True
    me = anon_client.get("/household/me", headers={"Authorization": f"Bearer {session['access_token']}"})
    assert me.json()[0]["customer_id"] == customer_id

    # A code works once.
    again = anon_client.post("/household/verify", json={"phone": "0700000001", "code": sent["demo_code"]})
    assert again.status_code == 400


def test_real_households_never_see_their_code(db, anon_client, caplog):
    add_household(db, "MTR-R", make_history([0.4] * 3))
    with caplog.at_level("INFO"):
        sent = anon_client.post("/household/request-code", json={"phone": PHONE}).json()
    assert sent["demo_code"] is None
    assert db.query(HouseholdCode).count() == 1
    assert "sign-in code is" not in caplog.text  # the SMS text is not logged


def test_unknown_numbers_get_the_same_answer_and_no_code(db, anon_client):
    r = anon_client.post("/household/request-code", json={"phone": "0788999999"})
    assert r.status_code == 200 and r.json()["demo_code"] is None
    assert db.query(HouseholdCode).count() == 0


def test_wrong_codes_are_limited(db, anon_client):
    demo_household(db)
    code = anon_client.post("/household/request-code", json={"phone": "0700000001"}).json()["demo_code"]
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(5):
        assert anon_client.post("/household/verify", json={"phone": "0700000001", "code": wrong}).status_code == 400
    # Five wrong tries use the code up, even for the right one.
    assert anon_client.post("/household/verify", json={"phone": "0700000001", "code": code}).status_code == 400


def test_codes_cannot_be_requested_again_at_once(db, anon_client):
    demo_household(db)
    assert anon_client.post("/household/request-code", json={"phone": "0700000001"}).status_code == 200
    r = anon_client.post("/household/request-code", json={"phone": "0700000001"})
    assert r.status_code == 429 and int(r.headers["retry-after"]) >= 1


def test_a_household_sees_only_its_own_account(db, household_client):
    mine = add_household(db, "MTR-A", make_history([0.4] * 3))
    theirs = add_household(db, "MTR-B", make_history([0.4] * 3), phone="+250788222333")
    assert household_client.get(f"/customers/{mine}").status_code == 200
    assert household_client.get(f"/customers/{theirs}").status_code == 404
    assert household_client.get(f"/customers/{theirs}/bills").status_code == 404
    assert household_client.get("/api/anomaly/flags", params={"household_id": "MTR-B"}).status_code == 404
    assert household_client.get("/api/anomaly/flags", params={"household_id": "MTR-A"}).status_code == 200
    r = household_client.post("/confirm-reading", json={"customer_id": theirs, "meter_id": "MTR-B", "confirmed_reading": "600"})
    assert r.status_code == 404
    # Own account, someone else's meter.
    r = household_client.post("/confirm-reading", json={"customer_id": mine, "meter_id": "MTR-B", "confirmed_reading": "600"})
    assert r.status_code == 404
    assert household_client.get("/customers").status_code == 401  # staff only


def test_a_staff_token_is_not_a_household_token(db, client):
    assert client.get("/household/me").status_code == 400


def test_household_token_stops_working_when_the_number_has_no_account(db, anon_client):
    r = anon_client.get("/household/me", headers={"Authorization": f"Bearer {household_token('+250788777666')}"})
    assert r.status_code == 401
