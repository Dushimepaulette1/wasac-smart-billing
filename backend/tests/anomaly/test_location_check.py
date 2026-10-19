"""Photos taken away from the meter, without a location, or uploaded go to an officer."""
from datetime import datetime, timedelta
import pytest
from app.anomaly.location import PhotoEvidence, check_location, distance_m
from app.models import ReadingEvidence
from app.models import Bill, Meter
from support.factories import add_household, make_history


METER_LAT, METER_LNG = -1.9441, 30.0619  # Kigali


def test_when_measuring_distance_should_be_right_to_a_few_metres():
    # 0.001 degrees of latitude is about 111 m.
    assert distance_m(-1.944, 30.06, -1.945, 30.06) == pytest.approx(111, abs=2)


@pytest.mark.parametrize("evidence, outcome", [
    (PhotoEvidence(lat=-1.9442, lng=30.0619, accuracy_m=20), "ok"),
    (PhotoEvidence(lat=-1.9441 - 0.003, lng=30.0619, accuracy_m=200), "ok"),  # 333 m away, but accuracy 200
    (PhotoEvidence(lat=-1.9541, lng=30.0619, accuracy_m=20), "far"),  # about 1.1 km
    (PhotoEvidence(), "no_location"),
    (PhotoEvidence(lat=-1.9442, lng=30.0619, accuracy_m=2000), "imprecise"),
    (PhotoEvidence(photo_source="upload", lat=-1.9442, lng=30.0619, accuracy_m=10), "upload"),
])
def test_when_checking_where_a_photo_was_taken_should_give_the_right_outcome(evidence, outcome):
    assert check_location(METER_LAT, METER_LNG, evidence).outcome == outcome


def test_when_the_meter_has_no_location_should_not_check_it():
    assert check_location(None, None, PhotoEvidence()).outcome == "not_checked"
    assert check_location(None, None, PhotoEvidence(photo_source="upload")).outcome == "upload"


@pytest.fixture
def household(db):
    start = datetime.utcnow() - timedelta(days=30 * 7)
    points = make_history([0.4] * 6, start=start)
    customer_id = add_household(db, "MTR-L", points)
    meter = db.get(Meter, "MTR-L")
    meter.gps_lat, meter.gps_lng = METER_LAT, METER_LNG
    db.commit()
    return customer_id, points[-1].reading_m3


def confirm(c, customer_id, value, **extra):
    return c.post("/confirm-reading", json={
        "customer_id": customer_id, "meter_id": "MTR-L", "confirmed_reading": f"{value:.3f}", **extra,
    })


def test_when_the_photo_is_taken_at_the_meter_should_bill_the_reading(db, household_client, household):
    customer_id, last = household
    body = confirm(household_client, customer_id, last + 12,
                   location={"lat": -1.9442, "lng": 30.0619, "accuracy_m": 15}).json()
    assert body["validation_status"] == "valid" and body["bill_id"]
    assert db.query(ReadingEvidence).one().outcome == "ok"


@pytest.mark.parametrize("extra, reason", [
    ({"location": {"lat": -1.9541, "lng": 30.0619, "accuracy_m": 15}}, "far"),
    ({}, "no_location"),
    ({"photo_source": "upload", "location": {"lat": -1.9442, "lng": 30.0619, "accuracy_m": 15}}, "upload"),
])
def test_when_the_photo_is_far_unlocated_or_uploaded_should_hold_it_for_an_officer(db, household_client, client, household, extra, reason):
    customer_id, last = household
    body = confirm(household_client, customer_id, last + 12, **extra).json()
    assert body["validation_status"] == "pending_review" and body.get("bill_id") is None
    assert body["anomaly"]["anomaly_type"] == "LOCATION_CHECK"
    assert body["anomaly"]["features"]["location_check"] == reason
    assert db.query(Bill).count() == 0 and db.get(Meter, "MTR-L").last_reading == last

    # The officer sees why, and can accept it: never rejected for this alone.
    item = client.get("/api/anomaly/review-queue").json()[0]
    assert item["flag"]["features"]["location_check"] == reason
    accepted = client.patch(f"/api/anomaly/flags/{item['flag']['id']}/resolve", json={"outcome": "accept"}).json()
    assert accepted["reading_status"] == "valid" and accepted["bill_id"]


def test_when_a_reading_is_held_for_another_reason_should_also_record_the_location(db, household_client, household):
    customer_id, last = household
    body = confirm(household_client, customer_id, last + 300).json()  # a spike, and no location
    assert body["anomaly"]["anomaly_type"] == "SPIKE"
    assert body["anomaly"]["features"]["location_check"] == "no_location"


def test_when_staff_enter_a_reading_should_not_check_the_location(db, client, household):
    customer_id, last = household
    body = confirm(client, customer_id, last + 12).json()
    assert body["validation_status"] == "valid"
    assert db.query(ReadingEvidence).count() == 0
