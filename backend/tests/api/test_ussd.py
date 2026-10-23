"""The USSD menu Africa's Talking serves (app/api/routes/ussd.py, app/services/ussd_menu.py)."""
from datetime import datetime, timedelta

import pytest

from app.models import Bill
from app.services.ussd_menu import parse_reading
from support.factories import add_household, make_history

PHONE = "+250788999000"
TOKEN = "test-ussd-token"


@pytest.fixture(autouse=True)
def ussd_token(monkeypatch):
    monkeypatch.setenv("USSD_CALLBACK_TOKEN", TOKEN)


@pytest.fixture
def household(db):
    start = datetime.utcnow() - timedelta(days=30 * 7)
    points = make_history([0.4] * 6, start=start)
    return add_household(db, "MTR-U", points, phone=PHONE), points[-1].reading_m3


def dial(c, text, phone=PHONE, token=TOKEN):
    """What Africa's Talking sends at each step: everything typed so far, joined by *."""
    r = c.post(f"/ussd?token={token}", data={"sessionId": "s1", "serviceCode": "*384*1#", "phoneNumber": phone, "text": text})
    return r.status_code, r.text


def digits(m3: float) -> str:
    return f"{round(m3 * 1000):08d}"


def test_when_the_token_is_missing_or_wrong_should_refuse_the_call(anon_client, household, monkeypatch):
    assert dial(anon_client, "", token="wrong")[0] == 403
    monkeypatch.delenv("USSD_CALLBACK_TOKEN")
    assert dial(anon_client, "", token="")[0] == 403  # not set up: off


def test_when_dialled_should_show_the_menu_in_kinyarwanda_then_english(anon_client, household):
    code, text = dial(anon_client, "")
    assert code == 200 and text.startswith("CON WASAC: fagitire y'amazi") and "9. English" in text
    assert dial(anon_client, "9")[1].startswith("CON WASAC water billing")


def test_when_a_normal_reading_is_sent_should_bill_it(anon_client, db, household):
    _, last = household
    reading = digits(last + 12)
    assert dial(anon_client, "9*1")[1].startswith("CON Type the 8 numbers")
    assert f"Reading: {last + 12:.3f} m3" in dial(anon_client, f"9*1*{reading}")[1]
    text = dial(anon_client, f"9*1*{reading}*1")[1]
    assert text.startswith("END Thank you. Reading:") and "Bill: RWF" in text
    assert db.query(Bill).count() == 1


def test_when_a_reading_is_a_spike_should_hold_it_for_an_officer(anon_client, household):
    _, last = household
    text = dial(anon_client, f"9*1*{digits(last + 300)}*1")[1]
    assert text.startswith("END Thank you. A WASAC officer is checking")
    # One reading at a time, as in the app.
    assert "still being checked" in dial(anon_client, "9*1")[1]


def test_when_the_reading_is_cancelled_or_malformed_should_send_nothing(anon_client, db, household):
    _, last = household
    assert dial(anon_client, f"9*1*{digits(last + 12)}*2")[1] == "END Cancelled. Nothing was sent."
    assert dial(anon_client, "9*1*123")[1].startswith("END Type 8 numbers only")
    assert db.query(Bill).count() == 0


def test_when_asking_for_the_bill_and_paying_should_answer_and_pay(anon_client, db, household):
    customer_id, _ = household
    assert dial(anon_client, "9*2")[1] == "END You have no bills yet."
    db.add(Bill(customer_id=customer_id, consumption_m3=12, amount_due=6460.0, payment_status="unpaid"))
    db.commit()
    assert "RWF 6,460, not paid" in dial(anon_client, "9*2")[1]
    assert dial(anon_client, "9*3")[1].startswith("CON Pay RWF 6,460 with MoMo")
    assert dial(anon_client, "9*3*1")[1] == "END Bill paid. Thank you."  # simulated without MoMo keys
    assert dial(anon_client, "9*3")[1] == "END You have no unpaid bill."


def test_when_the_number_has_no_account_should_say_so(anon_client, household):
    assert "not linked to a WASAC account" in dial(anon_client, "9*1", phone="+250788111222")[1]


def test_when_the_choice_is_not_on_the_menu_should_say_so(anon_client, household):
    assert dial(anon_client, "9*7")[1].startswith("END That choice is not on the menu")


@pytest.mark.parametrize("typed, value", [("00565846", 565.846), ("565.846", 565.846), ("565,846", 565.846),
                                         ("565846", None), ("abc", None), ("", None)])
def test_when_reading_typed_digits_should_accept_8_digits_or_a_decimal(typed, value):
    assert parse_reading(typed) == value
