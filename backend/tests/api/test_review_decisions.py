"""What an officer sees and leaves behind when deciding a held reading."""
from datetime import datetime, timedelta

import pytest

from app.anomaly.service import lock_meter
from app.models import Meter, Reading, StaffAction
from support.factories import add_household, make_history

METER = "MTR-RV"


@pytest.fixture
def household(db):
    points = make_history([0.4] * 6, start=datetime.utcnow() - timedelta(days=210))
    return add_household(db, METER, points), points[-1].reading_m3


def confirm(c, customer_id, value):
    return c.post("/confirm-reading", json={
        "customer_id": customer_id, "meter_id": METER, "confirmed_reading": f"{value:.3f}",
    }).json()


def audit(db, action):
    return db.query(StaffAction).filter(StaffAction.action == action).all()


def test_when_the_last_accepted_reading_was_flagged_should_show_it_as_the_previous_reading(db, client, household):
    customer_id, last = household
    # A reading billed but flagged for follow-up is still the reading billing goes on from.
    flagged = Reading(meter_id=METER, submitted_value=last + 12, implied_consumption=12.0,
                      validation_status="anomaly_flagged", submission_time=datetime.utcnow() - timedelta(days=3))
    db.add(flagged)
    lock_meter(db, METER).last_reading = last + 12
    db.commit()
    confirm(client, customer_id, last + 5)  # below it: held
    item = client.get("/api/anomaly/review-queue").json()[0]
    assert item["previous_reading_m3"] == pytest.approx(last + 12)
    assert item["history"][-1]["reading_m3"] == pytest.approx(last + 12)  # and it is in the history


def test_when_a_reading_is_held_should_not_show_later_readings_as_its_history(db, client, household):
    customer_id, last = household
    confirm(client, customer_id, last + 200)
    item = client.get("/api/anomaly/review-queue").json()[0]
    assert all(h["reading_m3"] <= last for h in item["history"])


def test_when_rejecting_without_a_reason_should_refuse_it(db, client, household):
    flag_id = confirm(client, household[0], household[1] + 200)["anomaly"]["flag_id"]
    for body in ({"outcome": "reject"}, {"outcome": "reject", "reason": "  "}):
        assert client.patch(f"/api/anomaly/flags/{flag_id}/resolve", json=body).status_code == 422
    assert db.query(Reading).filter(Reading.validation_status == "pending_review").count() == 1


def test_when_rejecting_should_keep_the_reason_in_the_audit_log(db, client, household):
    flag_id = confirm(client, household[0], household[1] + 200)["anomaly"]["flag_id"]
    r = client.patch(f"/api/anomaly/flags/{flag_id}/resolve", json={"outcome": "reject", "reason": "Digits do not match"})
    assert r.status_code == 200
    assert audit(db, "reject")[0].detail == f"{METER} SPIKE: Digits do not match"


def test_when_accepting_should_record_the_bill_in_the_audit_log(db, client, household):
    flag_id = confirm(client, household[0], household[1] + 200)["anomaly"]["flag_id"]
    bill_id = client.patch(f"/api/anomaly/flags/{flag_id}/resolve", json={"outcome": "accept"}).json()["bill_id"]
    assert f"bill {bill_id}, RWF" in audit(db, "accept")[0].detail


def test_when_staff_enter_a_reading_should_be_in_the_audit_log(db, client, household):
    confirm(client, household[0], household[1] + 12)
    row = audit(db, "reading_entered")[0]
    assert row.username == "officer1" and row.target == METER and "valid" in row.detail


def test_when_a_household_sends_a_reading_should_not_be_a_staff_action(db, household_client, household):
    confirm(household_client, household[0], household[1] + 12)
    assert audit(db, "reading_entered") == []


def test_when_the_average_is_worked_out_should_count_flagged_readings_but_not_corrections(db, client, household):
    customer_id, last = household
    db.add(Reading(meter_id=METER, submitted_value=last, submission_method="correction", validation_status="valid",
                   submission_time=datetime.utcnow() - timedelta(days=4)))
    db.add(Reading(meter_id=METER, submitted_value=last + 20, implied_consumption=20.0,
                   validation_status="anomaly_flagged", submission_time=datetime.utcnow() - timedelta(days=3)))
    db.commit()
    assert client.get(f"/customers/{customer_id}").json()["avg_consumption"] == 20.0


def test_when_rejected_with_a_code_should_show_it_to_the_household_but_not_the_officers_text(db, client, household_client, household):
    flag_id = confirm(client, household[0], household[1] + 200)["anomaly"]["flag_id"]
    client.patch(f"/api/anomaly/flags/{flag_id}/resolve",
                 json={"outcome": "reject", "reason": "Private note about the visit", "reason_code": "digits"})
    flag = household_client.get("/api/anomaly/flags", params={"household_id": METER}).json()[0]
    assert flag["decision_code"] == "digits" and "Private note" not in str(flag)


def test_when_a_reading_was_corrected_should_show_the_corrected_history_and_keep_the_original(db, client, household):
    from app.models import Bill, BillAdjustment, BillCorrection

    customer_id, last = household
    r = Reading(meter_id=METER, submitted_value=last + 12, corrected_value_m3=last + 10, implied_consumption=12.0,
                validation_status="valid", submission_time=datetime.utcnow() - timedelta(days=2))
    db.add(r)
    db.flush()
    bill = Bill(customer_id=customer_id, reading_id=r.reading_id, consumption_m3=12.0, amount_due=7000.0)
    fix = BillCorrection(customer_id=customer_id, reading_id=r.reading_id, value_before_m3=last + 12,
                         corrected_value_m3=last + 10, reason="Re-read", status="applied", requested_by="s", request_key="k")
    db.add_all([bill, fix])
    db.flush()
    db.add(BillAdjustment(correction_id=fix.id, bill_id=bill.bill_id, consumption_before=12.0, consumption_after=10.0,
                          amount_before=7000.0, amount_after=5000.0, amount_delta=-2000.0, tariff_version="v1-provisional"))
    db.commit()
    confirm(client, customer_id, last + 5)  # below it: held
    point = client.get("/api/anomaly/review-queue").json()[0]["history"][-1]
    assert point["reading_m3"] == pytest.approx(last + 10) and point["consumption_m3"] == 10.0
    assert point["original_reading_m3"] == pytest.approx(last + 12) and point["original_consumption_m3"] == 12.0
    assert client.get(f"/customers/{customer_id}").json()["avg_consumption"] == 10.0
