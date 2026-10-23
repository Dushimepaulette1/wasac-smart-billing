"""Reading a photo, live tips and confirming a reading (app/api/routes/readings.py)."""
import cv2
import pytest
from app.vision.models import ModelRegistry
from statistics import median
from app.anomaly.features import build_periods
from app.models import Bill, Meter, Reading
from support.factories import add_household
from support.vision_fakes import jpeg, meter_image, registry


def test_when_not_signed_in_should_refuse_the_photo_endpoints(anon_client):
    assert anon_client.post("/submit-photo", files={"file": ("m.jpg", b"x", "image/jpeg")}).status_code == 401
    assert anon_client.post("/guide-frame", files={"file": ("m.jpg", b"x", "image/jpeg")}).status_code == 401


def test_when_a_clear_photo_is_sent_should_return_the_reading(photo_client):
    client, _ = photo_client
    body = client.post("/submit-photo", files={"file": ("m.jpg", jpeg(meter_image()), "image/jpeg")}).json()
    assert body["status"] == "readable" and body["predicted_reading"] == "565846"
    assert body["confidence"] == 0.95 and body["quality_gate_score"] == pytest.approx(0.1)
    assert body["reading_digits"] == "00565846" and body["guidance"] == ["OK"]
    assert body["thumbnail_jpeg_base64"] and "measurements" not in body


def test_when_no_meter_is_in_the_photo_should_say_unreadable_not_fail(photo_client, cfg):
    client, holder = photo_client
    holder["reg"] = registry(cfg, dets=())
    r = client.post("/submit-photo", files={"file": ("m.jpg", jpeg(meter_image()), "image/jpeg")})
    assert r.status_code == 200
    assert r.json()["status"] == "unreadable" and r.json()["guidance"][0] == "NO_METER"
    assert r.json()["offer_manual_entry"]


def test_when_models_are_missing_should_offer_typing_the_reading(photo_client):
    client, holder = photo_client
    holder["reg"] = ModelRegistry()
    body = client.post("/submit-photo", files={"file": ("m.jpg", jpeg(meter_image()), "image/jpeg")}).json()
    assert body["models_ready"] is False and body["offer_manual_entry"] and body["status"] == "unreadable"


def test_when_the_upload_is_not_an_image_should_refuse_it(photo_client):
    client, _ = photo_client
    assert client.post("/submit-photo", files={"file": ("x.jpg", b"nope", "image/jpeg")}).status_code == 422


def test_when_a_live_frame_is_sent_should_return_tips(photo_client):
    client, _ = photo_client
    small = cv2.resize(meter_image(), (640, 480))
    body = client.post("/guide-frame", files={"file": ("f.jpg", jpeg(small), "image/jpeg")}).json()
    assert body["available"] and body["guidance"] == ["OK"] and body["box"]["x1"] == pytest.approx(0.25, abs=0.01)


DEMO_ID = "DEMO-MTR-002"


def test_when_a_normal_reading_is_confirmed_should_bill_it_and_report_no_anomaly(client, db, demo_histories):
    points = demo_histories[DEMO_ID]
    customer_id = add_household(db, DEMO_ID, points)
    daily = median(p.daily_consumption for p in build_periods(points))
    # Scored "now", long after the demo history ends, so per-day use is tiny: rules-only, no model on disk.
    submitted = round(points[-1].reading_m3 + daily * 30, 3)

    r = client.post("/confirm-reading", json={
        "customer_id": customer_id, "meter_id": DEMO_ID, "confirmed_reading": str(submitted),
    })
    assert r.status_code == 200
    body = r.json()
    assert body["success"] and body["bill_id"] and body["tariff_breakdown"]
    assert body["validation_status"] == "valid" and body["anomaly_flagged"] is False
    assert body["anomaly"]["anomaly_type"] == "NORMAL"

    stored = db.get(Reading, db.get(Bill, body["bill_id"]).reading_id)
    assert stored.validation_status == "valid" and stored.anomaly_score == 0.0
    assert db.get(Meter, DEMO_ID).last_reading == submitted


def test_when_a_confirmed_reading_is_a_spike_should_hold_it_for_review(client, db, demo_histories):
    points = demo_histories[DEMO_ID]
    customer_id = add_household(db, DEMO_ID, points)
    huge = 99_999.999  # the highest a meter shows: far above 5 m3/day whatever the gap
    body = client.post("/confirm-reading", json={
        "customer_id": customer_id, "meter_id": DEMO_ID, "confirmed_reading": str(huge),
    }).json()
    assert body["success"] and body["validation_status"] == "pending_review" and body["anomaly_flagged"]
    assert body["bill_id"] is None and body["bill_amount"] is None
    assert body["anomaly"]["anomaly_type"] == "SPIKE" and body["anomaly"]["pending_review"]
    assert db.get(Meter, DEMO_ID).last_reading == points[-1].reading_m3


@pytest.mark.parametrize("typed", ["nan", "inf", "1e3", "-5", "565.8461"])
def test_when_a_confirmed_reading_is_not_plain_digits_should_refuse_it(client, db, demo_histories, typed):
    customer_id = add_household(db, DEMO_ID, demo_histories[DEMO_ID])
    before = db.query(Reading).count()
    r = client.post("/confirm-reading", json={
        "customer_id": customer_id, "meter_id": DEMO_ID, "confirmed_reading": typed,
    })
    assert r.status_code == 422
    assert db.query(Reading).count() == before and db.query(Bill).count() == 0


@pytest.mark.parametrize("volume", ["NaN", "Infinity", -1, 1e9])
def test_when_a_bill_is_estimated_for_an_impossible_volume_should_refuse_it(client, volume):
    assert client.post("/calculate-bill", json={"consumption_m3": volume}).status_code == 422
