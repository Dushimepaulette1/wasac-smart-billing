"""evaluate_reading: every check a new reading goes through, without writing anything.
submit_reading stores what it decides, so the two must always agree."""
from datetime import datetime, timedelta

import pytest

from app.anomaly.location import PhotoEvidence
from app.anomaly.service import ReadingRefused, evaluate_reading, submit_reading
from app.models import AnomalyFlag, Bill, Meter, Reading, ReadingEvidence
from support.factories import add_household, make_history

METER = "MTR-E"
NEAR_PHOTO = PhotoEvidence(lat=-1.9442, lng=30.0619, accuracy_m=20)


@pytest.fixture
def household(db):
    """Six months at 0.4 m3/day, the last reading about 30 days ago."""
    points = make_history([0.4] * 6, start=datetime.utcnow() - timedelta(days=30 * 7))
    customer_id = add_household(db, METER, points)
    return customer_id, points[-1].reading_m3


def snapshot(db):
    return (
        db.query(Reading).count(), db.query(Bill).count(), db.query(AnomalyFlag).count(),
        db.query(ReadingEvidence).count(), db.get(Meter, METER).last_reading,
    )


def assert_nothing_written(db, before):
    assert not db.new and not db.dirty and not db.deleted
    assert snapshot(db) == before


# (reading relative to the last one, photo evidence, final type, held)
CASES = {
    "normal": (12.0, None, "NORMAL", False),
    "below last reading": (-1.0, None, "MISREAD_SUSPECTED", True),
    "spike": (200.0, None, "SPIKE", True),
    "photo needs a location check": (12.0, NEAR_PHOTO, "LOCATION_CHECK", True),  # the meter has no location yet
}


@pytest.mark.parametrize("delta, evidence, anomaly_type, held", CASES.values(), ids=CASES.keys())
def test_when_a_reading_is_evaluated_should_decide_without_writing_anything(
    db, household, delta, evidence, anomaly_type, held,
):
    _, last = household
    before = snapshot(db)
    meter = db.get(Meter, METER)
    result = evaluate_reading(db, meter, last + delta, datetime.utcnow(), evidence=evidence, household=True)
    assert result.refusal is None
    assert result.anomaly.anomaly_type == anomaly_type and result.anomaly.pending_review == held
    assert result.consumption_m3 == pytest.approx(delta)
    assert_nothing_written(db, before)


@pytest.mark.parametrize("delta, evidence, anomaly_type, held", CASES.values(), ids=CASES.keys())
def test_when_a_reading_is_submitted_should_store_what_the_evaluation_decided(
    db, household, delta, evidence, anomaly_type, held,
):
    customer_id, last = household
    meter = db.get(Meter, METER)
    preview = evaluate_reading(db, meter, last + delta, datetime.utcnow(), evidence=evidence, household=True)
    sub = submit_reading(db, meter, customer_id, last + delta, method="camera", evidence=evidence, household=True)
    assert sub.anomaly.anomaly_type == preview.anomaly.anomaly_type == anomaly_type
    assert sub.anomaly.pending_review == preview.anomaly.pending_review == held
    assert (sub.bill is None) == held
    assert (sub.reading.validation_status == "pending_review") == held
    assert (db.query(ReadingEvidence).count() == 1) == (evidence is not None)


def test_when_a_reading_is_waiting_for_an_officer_should_return_the_refusal_not_raise_it(db, household):
    _, last = household
    db.add(Reading(meter_id=METER, submitted_value=last + 5, submission_time=datetime.utcnow(),
                   validation_status="pending_review"))
    db.commit()
    before = snapshot(db)
    result = evaluate_reading(db, db.get(Meter, METER), last + 12, datetime.utcnow(), household=True)
    assert isinstance(result.refusal, ReadingRefused) and result.refusal.block.reason == "pending"
    assert result.anomaly is None
    assert_nothing_written(db, before)


def test_when_the_same_value_was_just_sent_should_return_a_duplicate_refusal(db, household):
    _, last = household
    db.add(Reading(meter_id=METER, submitted_value=last + 12, submission_time=datetime.utcnow() - timedelta(minutes=1),
                   validation_status="valid"))
    db.commit()
    before = snapshot(db)
    # Staff are not held to the reading window, but are still stopped from sending a value twice.
    result = evaluate_reading(db, db.get(Meter, METER), last + 12, datetime.utcnow(), household=False)
    assert result.refusal is not None and result.refusal.block is None
    assert_nothing_written(db, before)
