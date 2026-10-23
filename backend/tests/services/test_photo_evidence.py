"""The photo behind a reading, kept for reviewers (app/services/photo_evidence.py)."""
from datetime import datetime, timedelta

import pytest

from app.main import app as fastapi_app
from app.models import PhotoRead, Reading
from app.services.photo_evidence import purge
from app.vision.models import get_registry
from support.factories import add_household, make_history
from support.vision_fakes import jpeg, meter_image, registry

METER = "MTR-PH"
PHONE = "+250788000111"  # household_client's phone


@pytest.fixture
def household(db):
    start = datetime.utcnow() - timedelta(days=30 * 5)
    points = make_history([0.4] * 4, start=start, start_m3=565.0)
    return add_household(db, METER, points, phone=PHONE), points[-1].reading_m3


@pytest.fixture
def reader(household_client, cfg):
    fastapi_app.dependency_overrides[get_registry] = lambda: registry(cfg)  # reads 00565846
    return household_client


def send_photo(c):
    r = c.post("/submit-photo", files={"file": ("m.jpg", jpeg(meter_image()), "image/jpeg")})
    assert r.status_code == 200
    return r.json()["photo_id"]


def confirm(c, customer_id, value, photo_id):
    return c.post("/confirm-reading", json={
        "customer_id": customer_id, "meter_id": METER, "confirmed_reading": value, "photo_id": photo_id,
        "location": {"lat": -1.95, "lng": 30.06, "accuracy_m": 10},
    })


def test_when_a_photo_is_read_should_keep_it_with_what_the_reader_saw(reader, db, household):
    photo = db.get(PhotoRead, send_photo(reader))
    assert photo.owner == f"household:{PHONE}" and photo.image_jpeg[:2] == b"\xff\xd8"
    assert photo.reader_digits == "00565846" and photo.confidence_min == 0.95 and photo.reading_id is None


def test_when_the_household_confirms_should_link_the_photo_and_note_an_edit(reader, db, household):
    customer_id, _ = household
    photo_id = send_photo(reader)
    r = confirm(reader, customer_id, "00566.100", photo_id)  # not what the reader read
    assert r.status_code == 200
    photo = db.get(PhotoRead, photo_id)
    reading = db.get(Reading, photo.reading_id)
    assert reading.submitted_value == pytest.approx(566.1)
    assert photo.edited is True and reading.crnn_confidence == 0.95


def test_when_staff_review_a_held_reading_should_see_its_photo(reader, client, db, household):
    customer_id, _ = household
    photo_id = send_photo(reader)
    assert confirm(reader, customer_id, "00565.846", photo_id).status_code == 200  # first location: held
    item = next(i for i in client.get("/api/anomaly/review-queue").json() if i["flag"]["household_id"] == METER)
    assert item["photo_available"] and item["reader_digits"] == "00565846" and item["edited_by_household"] is False

    image = client.get(f"/api/anomaly/readings/{item['reading_id']}/photo")
    assert image.status_code == 200 and image.headers["content-type"] == "image/jpeg"
    assert image.headers["cache-control"] == "private, no-store"
    assert reader.get(f"/api/anomaly/readings/{item['reading_id']}/photo").status_code == 401  # households: no


def test_when_a_photo_id_is_someone_elses_or_used_should_ignore_it(reader, db, household):
    customer_id, _ = household
    other = PhotoRead(id="f" * 32, owner="household:+250788999999", reader_digits="00565846")
    db.add(other)
    db.commit()
    assert confirm(reader, customer_id, "00565.846", other.id).status_code == 200
    assert db.get(PhotoRead, other.id).reading_id is None


def test_when_photos_are_old_should_drop_unconfirmed_ones_and_the_images_of_kept_ones(db, monkeypatch):
    monkeypatch.setenv("PHOTO_RETENTION_DAYS", "90")
    now = datetime(2026, 10, 23)
    db.add(Reading(reading_id=7, meter_id="M", submitted_value=1.0))
    db.add_all([
        PhotoRead(id="a" * 32, owner="x", created_at=now - timedelta(days=2), image_jpeg=b"j"),  # never used
        PhotoRead(id="b" * 32, owner="x", created_at=now - timedelta(days=91), image_jpeg=b"j", reading_id=7),
        PhotoRead(id="c" * 32, owner="x", created_at=now - timedelta(hours=2), image_jpeg=b"j"),  # just sent
    ])
    db.commit()
    purge(db, now)
    db.commit()
    db.expire_all()
    assert db.get(PhotoRead, "a" * 32) is None
    assert db.get(PhotoRead, "b" * 32).image_jpeg is None and db.get(PhotoRead, "b" * 32).reading_id == 7
    assert db.get(PhotoRead, "c" * 32).image_jpeg == b"j"
