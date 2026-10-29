"""The household changes the photo reader's digits (app/anomaly/edits.py). Only a value 1 m³ or more
below a complete, reliable AI read is held for that reason; every other rule still runs on the
household's value; an unreliable or missing AI read is never a reason to hold or to approve."""
from datetime import datetime, timedelta

import pytest

from app.anomaly.config import AnomalyConfig
from app.anomaly.edits import changed_positions, check_edit, household_digits
from app.models import Bill, PhotoRead, Reading
from support.factories import add_household, make_history

METER = "MTR-ED"
# The brief's household: previous accepted reading 00431460, about 30 days ago, using 0.4 m3/day.
LAST = 431.460


@pytest.fixture
def household(db):
    points = make_history([0.4] * 4, start=datetime.utcnow() - timedelta(days=150), start_m3=LAST - 48)
    assert points[-1].reading_m3 == pytest.approx(LAST)
    return add_household(db, METER, points)


def photo(db, digits, guidance="OK", owner="staff:officer1", pid="p1"):
    db.add(PhotoRead(id=pid, owner=owner, reader_digits=digits, confidence_min=0.9, guidance=guidance))
    db.commit()
    return pid


def confirm(client, customer_id, value, photo_id):
    # Staff enter it, so the photo-location check does not hold it (households: test_location_check.py).
    return client.post("/confirm-reading", json={
        "customer_id": customer_id, "meter_id": METER, "confirmed_reading": f"{value:.3f}", "photo_id": photo_id,
    }).json()


def test_the_briefs_scenario_should_be_held_as_lower_than_the_previous_reading_with_both_values(db, client, household):
    body = confirm(client, household, 431.400, photo(db, "00431520"))
    assert body["validation_status"] == "pending_review" and body["bill_id"] is None
    assert body["anomaly"]["anomaly_type"] == "MISREAD_SUSPECTED"  # below the previous reading wins
    f = body["anomaly"]["features"]
    assert f["ai_digits"] == "00431520" and f["household_digits"] == "00431400" and f["edited"] is True
    assert f["ai_reliable"] is True and f["edit_lowered_m3"] == pytest.approx(0.12)


@pytest.mark.parametrize("value, held", [(442.520, True), (442.530, False)])
def test_when_a_reliable_read_is_lowered_should_hold_from_1_m3(db, client, household, value, held):
    body = confirm(client, household, value, photo(db, "00443520"))
    assert (body["anomaly"]["anomaly_type"] == "EDITED_DOWN") == held
    assert (body["validation_status"] == "pending_review") == held
    assert (body["bill_id"] is None) == held


def test_when_only_litre_wheels_are_changed_should_bill_as_usual(db, client, household):
    body = confirm(client, household, 443.480, photo(db, "00443520"))
    assert body["validation_status"] == "valid" and body["bill_id"]
    assert body["anomaly"]["features"]["edited"] is True  # still recorded


def test_when_a_read_is_corrected_upward_should_bill_as_usual(db, client, household):
    body = confirm(client, household, 444.000, photo(db, "00443520"))
    assert body["validation_status"] == "valid" and body["bill_id"]


def test_when_an_upward_correction_gives_unusually_high_use_should_still_hold_it(db, client, household):
    body = confirm(client, household, 480.000, photo(db, "00443520"))  # ~1.6 m3/day, 4x usual
    assert body["anomaly"]["anomaly_type"] == "SPIKE" and body["validation_status"] == "pending_review"
    assert body["anomaly"]["features"]["ai_digits"] == "00443520"


@pytest.mark.parametrize("digits, guidance", [
    ("00448520", "CHECK_NUMBERS"),  # the reader was unsure
    ("00448520", "HARD_TO_READ"),   # the quality gate
    ("448520", "OK"),               # incomplete
    (None, "NO_METER"),             # nothing read
])
def test_when_the_ai_read_is_missing_or_unreliable_should_not_hold_for_the_difference(db, client, household, digits, guidance):
    body = confirm(client, household, 443.000, photo(db, digits, guidance))  # 5 m3 below the read
    assert body["validation_status"] == "valid" and body["anomaly"]["anomaly_type"] != "EDITED_DOWN"
    assert body["anomaly"]["features"]["ai_reliable"] is False


def test_when_the_household_matches_the_ai_read_should_still_apply_every_rule(db, client, household):
    body = confirm(client, household, 431.000, photo(db, "00431000"))  # matches the AI, but lower than before
    assert body["anomaly"]["anomaly_type"] == "MISREAD_SUSPECTED" and body["validation_status"] == "pending_review"
    assert body["anomaly"]["features"]["edited"] is False


def test_when_someone_elses_photo_is_sent_should_ignore_it(db, client, household):
    pid = photo(db, "00450000", owner="household:+250788999999")
    body = confirm(client, household, 443.000, pid)
    assert body["validation_status"] == "valid" and "ai_digits" not in body["anomaly"]["features"]
    assert db.get(PhotoRead, pid).reading_id is None


def test_when_a_reading_is_stored_should_link_its_photo_in_the_same_transaction(db, client, household):
    pid = photo(db, "00443520")
    body = confirm(client, household, 443.480, pid)
    stored = db.get(PhotoRead, pid)
    assert stored.reading_id == db.query(Bill).filter(Bill.bill_id == body["bill_id"]).one().reading_id
    assert stored.edited is True and db.get(Reading, stored.reading_id).crnn_confidence == 0.9


def test_when_a_held_edit_is_reviewed_should_show_which_wheels_changed(db, client, household):
    confirm(client, household, 442.520, photo(db, "00443520"))
    item = client.get("/api/anomaly/review-queue").json()[0]
    assert item["flag"]["anomaly_type"] == "EDITED_DOWN"
    assert item["reader_digits"] == "00443520" and item["household_digits"] == "00442520"
    assert item["changed_positions"] == [4]


def test_helpers():
    cfg = AnomalyConfig()
    assert household_digits(565.846, cfg) == "00565846"
    assert changed_positions("00443520", "00442520") == [4]
    assert changed_positions(None, "00442520") == [] and changed_positions("443520", "00442520") == []
    assert check_edit("00443520", "OK,GLARE", 442.52, cfg).hold
    assert not check_edit("00443520", "GLARE,CHECK_NUMBERS", 442.52, cfg).hold


def test_when_the_edit_threshold_is_configured_should_use_it(monkeypatch):
    monkeypatch.setenv("ANOMALY_EDIT_HOLD_M3", "2")
    cfg = AnomalyConfig.from_env()
    assert not check_edit("00443520", "OK", 442.52, cfg).hold
    assert check_edit("00443520", "OK", 441.52, cfg).hold
