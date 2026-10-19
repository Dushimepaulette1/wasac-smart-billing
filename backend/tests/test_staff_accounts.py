"""Roles, the audit log and staff accounts (app/api/routes/staff_auth.py)."""
import pytest

from conftest import add_household, add_officer, make_history, signed_in_client

from app.models import StaffAction
from app.api.routes.staff_auth import temporary_password


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


def test_sign_ins_and_failures_are_logged(db, anon_client):
    add_officer(db)
    anon_client.post("/auth/login", json={"username": "officer1", "password": "nope"})
    anon_client.post("/auth/login", json={"username": "officer1", "password": "correct horse"})
    assert actions(db) == [("officer1", "sign_in_failed", None), ("officer1", "sign_in", None)]


def test_a_very_long_typed_username_is_still_logged(db, anon_client):
    anon_client.post("/auth/login", json={"username": "x" * 500, "password": "nope"})
    assert db.query(StaffAction).one().username == "x" * 64


def test_review_decisions_are_logged(db, client):
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


def test_officers_see_only_their_own_activity(db, as_role):
    officer = as_role("officer")
    add_officer(db, username="someone")
    db.add(StaffAction(username="someone", action="sign_in"))
    db.add(StaffAction(username="officer", action="sign_in"))
    db.commit()
    assert [a["username"] for a in officer.get("/auth/activity").json()] == ["officer"]
    supervisor = as_role("supervisor")
    assert {a["username"] for a in supervisor.get("/auth/activity").json()} == {"officer", "someone"}
    assert [a["username"] for a in supervisor.get("/auth/activity?username=someone").json()] == ["someone"]


def test_only_admins_manage_accounts(db, as_role):
    for role in ("officer", "supervisor"):
        c = as_role(role)
        assert c.get("/auth/staff").status_code == 403
        assert c.post("/auth/staff", json={"username": "new.one", "full_name": "New"}).status_code == 403


def test_admin_creates_an_account_with_a_temporary_password(db, as_role, anon_client):
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


def test_disabling_an_account_stops_its_session(db, as_role):
    admin = as_role("admin")
    officer = as_role("officer")
    assert officer.get("/auth/me").status_code == 200
    r = admin.patch("/auth/staff/officer", json={"is_active": False})
    assert r.status_code == 200 and r.json()["is_active"] is False
    assert officer.get("/auth/me").status_code == 401
    assert ("admin", "account_updated", "officer") in actions(db)


def test_admins_cannot_lock_themselves_out(db, as_role):
    admin = as_role("admin")
    assert admin.patch("/auth/staff/admin", json={"is_active": False}).status_code == 400
    assert admin.patch("/auth/staff/admin", json={"role": "officer"}).status_code == 400
    assert admin.patch("/auth/staff/admin", json={"full_name": "Renamed"}).status_code == 200


def test_reset_password_gives_a_new_working_password(db, as_role, anon_client):
    admin = as_role("admin")
    add_officer(db, username="forgot")
    r = admin.post("/auth/staff/forgot/reset-password")
    assert r.status_code == 200
    new = r.json()["temporary_password"]
    assert anon_client.post("/auth/login", json={"username": "forgot", "password": "correct horse"}).status_code == 401
    assert anon_client.post("/auth/login", json={"username": "forgot", "password": new}).status_code == 200
    assert admin.post("/auth/staff/ghost/reset-password").status_code == 404


def test_change_own_password(db, client, anon_client):
    assert client.post("/auth/password", json={"current_password": "wrong", "new_password": "a long new one"}).status_code == 400
    assert client.post("/auth/password", json={"current_password": "correct horse", "new_password": "short"}).status_code == 400
    assert client.post("/auth/password", json={"current_password": "correct horse", "new_password": "a long new one"}).status_code == 204
    assert anon_client.post("/auth/login", json={"username": "officer1", "password": "a long new one"}).status_code == 200


def test_temporary_passwords_are_readable_and_different():
    a, b = temporary_password(), temporary_password()
    assert a != b and len(a) == 14 and a.count("-") == 2
    assert not set(a) & set("0O1lI")
