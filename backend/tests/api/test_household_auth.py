"""Household sign-in with a one-time code, and households seeing only their own account."""
from app.models import HouseholdCode
from support.factories import add_household, household_token, make_history


def test_when_not_signed_in_should_refuse_household_routes(db, anon_client):
    add_household(db, "MTR-H", make_history([1.0] * 3))
    assert anon_client.get("/api/anomaly/flags", params={"household_id": "MTR-H"}).status_code == 401
    assert anon_client.get("/customers/CUST-H").status_code == 401
    assert anon_client.post("/api/anomaly/score", json={"household_id": "MTR-H", "reading_digits": "1"}).status_code == 401


PHONE = "+250788000111"  # add_household's default


def demo_household(db, meter_id="DEMO-MTR-001", phone="+250700000001"):
    return add_household(db, meter_id, make_history([0.4] * 3), phone=phone)


def test_when_a_demo_household_requests_a_code_should_show_it_and_accept_it_once(db, anon_client):
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


def test_when_a_real_household_requests_a_code_should_never_show_or_log_it(db, anon_client, caplog):
    add_household(db, "MTR-R", make_history([0.4] * 3))
    with caplog.at_level("INFO"):
        sent = anon_client.post("/household/request-code", json={"phone": PHONE}).json()
    assert sent["demo_code"] is None
    assert db.query(HouseholdCode).count() == 1
    assert "sign-in code is" not in caplog.text  # the SMS text is not logged


def test_when_the_number_is_unknown_should_say_so_and_store_no_code(db, anon_client):
    r = anon_client.post("/household/request-code", json={"phone": "0788999999"})
    assert r.status_code == 404 and "not linked to a WASAC account" in r.json()["detail"]
    assert db.query(HouseholdCode).count() == 0


def test_when_many_unknown_numbers_are_tried_should_slow_the_caller_down(db, anon_client):
    codes = [anon_client.post("/household/request-code", json={"phone": f"078899990{i}"}).status_code for i in range(6)]
    assert codes[:5] == [404] * 5 and codes[5] == 429  # 5 per IP per 15 minutes


def test_when_a_wrong_code_is_tried_five_times_should_use_the_code_up(db, anon_client):
    demo_household(db)
    code = anon_client.post("/household/request-code", json={"phone": "0700000001"}).json()["demo_code"]
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(5):
        assert anon_client.post("/household/verify", json={"phone": "0700000001", "code": wrong}).status_code == 400
    # Five wrong tries use the code up, even for the right one.
    assert anon_client.post("/household/verify", json={"phone": "0700000001", "code": code}).status_code == 400


def test_when_a_new_code_is_requested_at_once_should_ask_to_wait(db, anon_client):
    demo_household(db)
    assert anon_client.post("/household/request-code", json={"phone": "0700000001"}).status_code == 200
    r = anon_client.post("/household/request-code", json={"phone": "0700000001"})
    assert r.status_code == 429 and int(r.headers["retry-after"]) >= 1


def test_when_a_household_asks_for_another_account_should_return_404(db, household_client):
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


def test_when_a_staff_token_asks_for_household_me_should_refuse_it(db, client):
    assert client.get("/household/me").status_code == 400


def test_when_the_number_has_no_account_should_reject_the_token(db, anon_client):
    r = anon_client.get("/household/me", headers={"Authorization": f"Bearer {household_token('+250788777666')}"})
    assert r.status_code == 401
