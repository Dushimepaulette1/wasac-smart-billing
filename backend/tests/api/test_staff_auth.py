"""Staff sign-in, roles, staff accounts and the activity log (app/api/routes/staff_auth.py)."""
import time
import pytest
from app.models import StaffAction
from app.api.routes.staff_auth import temporary_password
from support.factories import add_household, add_officer, make_history
from support.clients import signed_in_client


def test_when_staff_sign_in_should_return_a_token_that_opens_me(db, anon_client):
    add_officer(db, full_name="Uwase Jeanne")
    r = anon_client.post("/auth/login", json={"username": " Officer1 ", "password": "correct horse"})
    assert r.status_code == 200
    body = r.json()
    assert body["user"] == {"username": "officer1", "full_name": "Uwase Jeanne", "role": "officer"}
    assert body["expires_at"] > time.time()
    me = anon_client.get("/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.json()["username"] == "officer1"


def test_when_the_password_or_username_is_wrong_should_give_the_same_answer(db, anon_client):
    add_officer(db)
    bad_pw = anon_client.post("/auth/login", json={"username": "officer1", "password": "nope"})
    no_user = anon_client.post("/auth/login", json={"username": "ghost", "password": "nope"})
    assert bad_pw.status_code == no_user.status_code == 401
    assert bad_pw.json() == no_user.json()


def test_when_the_account_is_turned_off_should_refuse_sign_in(db, anon_client):
    add_officer(db, active=False)
    assert anon_client.post("/auth/login", json={"username": "officer1", "password": "correct horse"}).status_code == 401


def test_when_sign_in_fails_five_times_should_lock_the_account(db, anon_client):
    add_officer(db)
    for _ in range(5):
        anon_client.post("/auth/login", json={"username": "officer1", "password": "nope"})
    r = anon_client.post("/auth/login", json={"username": "officer1", "password": "correct horse"})
    assert r.status_code == 429


def test_when_no_staff_token_is_sent_should_refuse_staff_routes(db, anon_client):
    assert anon_client.get("/customers").status_code == 401
    assert anon_client.get("/api/anomaly/flags").status_code == 401
    assert anon_client.get("/api/anomaly/review-queue").status_code == 401
    assert anon_client.patch("/api/anomaly/flags/1/resolve", json={"outcome": "accept"}).status_code == 401
    assert anon_client.get("/auth/me", headers={"Authorization": "Bearer forged.token"}).status_code == 401


@pytest.fixture
def as_role(db):
    """as_role("admin") -> a client signed in with that role."""
    apps = []

    def make(role, username=None):
        username = username or role
        add_officer(db, username=username, full_name=role.title(), role=role)
        fastapi_app, client = signed_in_client(db, username)
        apps.append(fastapi_app)
        return client

    yield make
    for fastapi_app in apps:
        fastapi_app.dependency_overrides.clear()


def actions(db):
    return [(a.username, a.action, a.target) for a in db.query(StaffAction).order_by(StaffAction.id)]


def test_when_staff_sign_in_or_fail_should_log_it(db, anon_client):
    add_officer(db)
    anon_client.post("/auth/login", json={"username": "officer1", "password": "nope"})
    anon_client.post("/auth/login", json={"username": "officer1", "password": "correct horse"})
    assert actions(db) == [("officer1", "sign_in_failed", None), ("officer1", "sign_in", None)]


def test_when_a_very_long_username_is_typed_should_still_log_it(db, anon_client):
    anon_client.post("/auth/login", json={"username": "x" * 500, "password": "nope"})
    assert db.query(StaffAction).one().username == "x" * 64


def test_when_an_officer_decides_should_log_the_decision(db, client):
    from datetime import datetime, timedelta

    start = datetime.utcnow() - timedelta(days=30 * 7)
    points = make_history([0.4] * 6, start=start)
    customer_id = add_household(db, "MTR900", points)
    held = client.post("/confirm-reading", json={
        "customer_id": customer_id, "meter_id": "MTR900", "confirmed_reading": str(round(points[-1].reading_m3 + 200, 3)),
    }).json()
    flag_id = held["anomaly"]["flag_id"]
    assert client.patch(f"/api/anomaly/flags/{flag_id}/resolve", json={"outcome": "reject"}).status_code == 200
    assert ("officer1", "reject", f"flag {flag_id}") in actions(db)


def test_when_an_officer_opens_activity_should_see_only_their_own(db, as_role):
    officer = as_role("officer")
    add_officer(db, username="someone")
    db.add(StaffAction(username="someone", action="sign_in"))
    db.add(StaffAction(username="officer", action="sign_in"))
    db.commit()
    assert [a["username"] for a in officer.get("/auth/activity").json()] == ["officer"]
    supervisor = as_role("supervisor")
    assert {a["username"] for a in supervisor.get("/auth/activity").json()} == {"officer", "someone"}
    assert [a["username"] for a in supervisor.get("/auth/activity?username=someone").json()] == ["someone"]


def test_when_a_non_admin_manages_accounts_should_refuse_it(db, as_role):
    for role in ("officer", "supervisor"):
        c = as_role(role)
        assert c.get("/auth/staff").status_code == 403
        assert c.post("/auth/staff", json={"username": "new.one", "full_name": "New"}).status_code == 403


def test_when_an_admin_adds_an_account_should_issue_a_working_temporary_password(db, as_role, anon_client):
    admin = as_role("admin")
    r = admin.post("/auth/staff", json={"username": " New.One ", "full_name": "Mukamana Alice", "role": "supervisor"})
    assert r.status_code == 201
    body = r.json()
    assert body["account"]["username"] == "new.one" and body["account"]["role"] == "supervisor"
    login = anon_client.post("/auth/login", json={"username": "new.one", "password": body["temporary_password"]})
    assert login.status_code == 200
    assert ("admin", "account_created", "new.one") in actions(db)
    assert admin.post("/auth/staff", json={"username": "new.one", "full_name": "X"}).status_code == 409
    assert admin.post("/auth/staff", json={"username": "a b", "full_name": "X"}).status_code == 400
    listed = admin.get("/auth/staff").json()
    assert next(a for a in listed if a["username"] == "new.one")["last_sign_in"] is not None


def test_when_an_account_is_turned_off_should_end_its_session(db, as_role):
    admin = as_role("admin")
    officer = as_role("officer")
    assert officer.get("/auth/me").status_code == 200
    r = admin.patch("/auth/staff/officer", json={"is_active": False})
    assert r.status_code == 200 and r.json()["is_active"] is False
    assert officer.get("/auth/me").status_code == 401
    assert ("admin", "account_updated", "officer") in actions(db)


def test_when_admins_change_their_own_role_or_status_should_refuse_it(db, as_role):
    admin = as_role("admin")
    assert admin.patch("/auth/staff/admin", json={"is_active": False}).status_code == 400
    assert admin.patch("/auth/staff/admin", json={"role": "officer"}).status_code == 400
    assert admin.patch("/auth/staff/admin", json={"full_name": "Renamed"}).status_code == 200


def test_when_a_password_is_reset_should_give_a_new_working_one(db, as_role, anon_client):
    admin = as_role("admin")
    add_officer(db, username="forgot")
    r = admin.post("/auth/staff/forgot/reset-password")
    assert r.status_code == 200
    new = r.json()["temporary_password"]
    assert anon_client.post("/auth/login", json={"username": "forgot", "password": "correct horse"}).status_code == 401
    assert anon_client.post("/auth/login", json={"username": "forgot", "password": new}).status_code == 200
    assert admin.post("/auth/staff/ghost/reset-password").status_code == 404


def test_when_staff_change_their_password_should_check_the_old_one_and_the_length(db, client, anon_client):
    assert client.post("/auth/password", json={"current_password": "wrong", "new_password": "a long new one"}).status_code == 400
    assert client.post("/auth/password", json={"current_password": "correct horse", "new_password": "short"}).status_code == 400
    assert client.post("/auth/password", json={"current_password": "correct horse", "new_password": "a long new one"}).status_code == 204
    assert anon_client.post("/auth/login", json={"username": "officer1", "password": "a long new one"}).status_code == 200


def test_when_making_temporary_passwords_should_be_readable_and_different():
    a, b = temporary_password(), temporary_password()
    assert a != b and len(a) == 14 and a.count("-") == 2
    assert not set(a) & set("0O1lI")


def test_when_staff_list_households_should_include_their_unpaid_bills(db, client):
    from app.models import Bill

    add_household(db, "MTR-P", make_history([0.4] * 3))
    db.add_all([
        Bill(customer_id="CUST-P", consumption_m3=10, amount_due=5000.0, payment_status="unpaid"),
        Bill(customer_id="CUST-P", consumption_m3=12, amount_due=6200.5, payment_status="unpaid"),
        Bill(customer_id="CUST-P", consumption_m3=9, amount_due=4000.0, payment_status="paid"),
    ])
    db.commit()
    row = next(c for c in client.get("/customers").json() if c["customer_id"] == "CUST-P")
    assert row["unpaid_count"] == 2 and row["unpaid_amount"] == 11200.5
