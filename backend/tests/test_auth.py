import time

from conftest import add_household, add_officer, make_history

from auth.security import hash_password, make_token, read_token, verify_password


def test_password_hash_round_trip_and_salt():
    stored = hash_password("s3cret pass", iterations=1000)
    assert verify_password("s3cret pass", stored)
    assert not verify_password("wrong", stored)
    assert hash_password("s3cret pass", iterations=1000) != stored  # salted
    assert not verify_password("x", "not-a-hash")


def test_token_round_trip_expiry_and_tamper():
    token, exp = make_token("officer1", now=1000, ttl=60)
    assert exp == 1060
    assert read_token(token, now=1030) == "officer1"
    assert read_token(token, now=1061) is None
    payload, sig = token.split(".")
    assert read_token(payload + "." + sig[:-2] + "AA", now=1030) is None
    assert read_token("garbage", now=1030) is None


def test_login_returns_token_and_me(db, anon_client):
    add_officer(db, full_name="Uwase Jeanne")
    r = anon_client.post("/auth/login", json={"username": " Officer1 ", "password": "correct horse"})
    assert r.status_code == 200
    body = r.json()
    assert body["user"] == {"username": "officer1", "full_name": "Uwase Jeanne", "role": "officer"}
    assert body["expires_at"] > time.time()
    me = anon_client.get("/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.json()["username"] == "officer1"


def test_wrong_password_and_unknown_user_get_the_same_answer(db, anon_client):
    add_officer(db)
    bad_pw = anon_client.post("/auth/login", json={"username": "officer1", "password": "nope"})
    no_user = anon_client.post("/auth/login", json={"username": "ghost", "password": "nope"})
    assert bad_pw.status_code == no_user.status_code == 401
    assert bad_pw.json() == no_user.json()


def test_inactive_officer_cannot_sign_in(db, anon_client):
    add_officer(db, active=False)
    assert anon_client.post("/auth/login", json={"username": "officer1", "password": "correct horse"}).status_code == 401


def test_repeated_failures_lock_the_account(db, anon_client):
    add_officer(db)
    for _ in range(5):
        anon_client.post("/auth/login", json={"username": "officer1", "password": "nope"})
    r = anon_client.post("/auth/login", json={"username": "officer1", "password": "correct horse"})
    assert r.status_code == 429


def test_staff_routes_need_a_token(db, anon_client):
    assert anon_client.get("/customers").status_code == 401
    assert anon_client.get("/api/anomaly/flags").status_code == 401
    assert anon_client.get("/api/anomaly/review-queue").status_code == 401
    assert anon_client.patch("/api/anomaly/flags/1/resolve", json={"outcome": "accept"}).status_code == 401
    assert anon_client.get("/auth/me", headers={"Authorization": "Bearer forged.token"}).status_code == 401


def test_household_routes_need_a_sign_in(db, anon_client):
    add_household(db, "MTR-H", make_history([1.0] * 3))
    assert anon_client.get("/api/anomaly/flags", params={"household_id": "MTR-H"}).status_code == 401
    assert anon_client.get("/customers/CUST-H").status_code == 401
    assert anon_client.post("/api/anomaly/score", json={"household_id": "MTR-H", "reading_digits": "1"}).status_code == 401


def test_review_queue_lists_held_readings_with_context(db, client):
    from anomaly.db_models import AnomalyFlag
    from database import Reading

    add_household(db, "MTR-Q", make_history([1.0] * 4))
    reading = Reading(meter_id="MTR-Q", submitted_value=900.0, validation_status="pending_review")
    db.add(reading)
    db.flush()
    db.add(AnomalyFlag(household_id="MTR-Q", reading_id=reading.reading_id, anomaly_type="SPIKE",
                       requires_staff_review=True, status="open"))
    db.commit()
    items = client.get("/api/anomaly/review-queue").json()
    assert len(items) == 1
    assert items[0]["reading_m3"] == 900.0
    assert items[0]["flag"]["anomaly_type"] == "SPIKE"
    assert isinstance(items[0]["history"], list)
