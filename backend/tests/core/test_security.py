"""Password hashing and signed tokens (app/core/security.py)."""
from app.core.security import hash_password, make_token, read_token, verify_password


def test_when_a_password_is_hashed_should_verify_it_and_salt_each_hash():
    stored = hash_password("s3cret pass", iterations=1000)
    assert verify_password("s3cret pass", stored)
    assert not verify_password("wrong", stored)
    assert hash_password("s3cret pass", iterations=1000) != stored  # salted
    assert not verify_password("x", "not-a-hash")


def test_when_a_token_is_expired_or_tampered_with_should_reject_it():
    token, exp = make_token("officer1", now=1000, ttl=60)
    assert exp == 1060
    assert read_token(token, now=1030) == "officer1"
    assert read_token(token, now=1061) is None
    payload, sig = token.split(".")
    assert read_token(payload + "." + sig[:-2] + "AA", now=1030) is None
    assert read_token("garbage", now=1030) is None
