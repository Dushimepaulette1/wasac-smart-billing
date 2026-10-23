"""Test HTTP clients for the app, with the test database swapped in."""


def _test_client(db, headers=None):
    from fastapi.testclient import TestClient

    from app.db.session import get_db
    from app.main import app as fastapi_app

    def override():
        yield db

    fastapi_app.dependency_overrides[get_db] = override
    # no context manager: lifespan (Postgres init_db) is not run
    return fastapi_app, TestClient(fastapi_app, headers=headers or {})


def signed_in_client(db, username):
    """A client signed in as an existing staff user; the caller clears fastapi_app.dependency_overrides."""
    from app.models import StaffUser
    from support.factories import staff_token

    user = db.query(StaffUser).filter(StaffUser.username == username).one()
    return _test_client(db, {"Authorization": f"Bearer {staff_token(user)}"})
