"""Africa's Talking SMS (app/services/sms.py) and sign-in codes by SMS. No real requests."""
import httpx
import pytest
from app.services import sms
from app.models import HouseholdCode
from support.factories import add_household, make_history


KEY = "atsk_secret_key_for_tests"


class FakeResponse:
    def __init__(self, status_code=201, body=None, text=""):
        self.status_code = status_code
        self.is_success = 200 <= status_code < 300
        self._body = body
        self.text = text

    def json(self):
        if self._body is None:
            raise ValueError("not json")
        return self._body


def accepted(phone="+250788000111"):
    return FakeResponse(201, {"SMSMessageData": {"Recipients": [
        {"statusCode": 101, "status": "Success", "number": phone, "messageId": "ATX1", "cost": "RWF 0"}]}})


@pytest.fixture
def sandbox(monkeypatch):
    monkeypatch.setenv("AT_USERNAME", "sandbox")
    monkeypatch.setenv("AT_API_KEY", KEY)
    calls = []

    def post(url, data, headers, timeout):
        calls.append({"url": url, "data": data, "headers": headers})
        return calls_answer[0]

    calls_answer = [accepted()]
    monkeypatch.setattr(sms.httpx, "post", post)
    return calls, calls_answer


def test_when_no_keys_are_set_should_send_nothing(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("must not call Africa's Talking")

    monkeypatch.setattr(sms.httpx, "post", boom)
    assert sms.send_sms("+250788000111", "hello") is False


def test_when_the_username_is_sandbox_should_use_the_sandbox_and_hide_key_and_number(sandbox, caplog):
    calls, _ = sandbox
    with caplog.at_level("INFO"):
        assert sms.send_sms("+250788000111", "Your bill is ready") is True
    call = calls[0]
    assert call["url"] == sms.SANDBOX_URL
    assert call["data"] == {"username": "sandbox", "to": "+250788000111", "message": "Your bill is ready"}
    assert call["headers"]["apiKey"] == KEY
    assert KEY not in caplog.text and "+250788000111" not in caplog.text  # key never, number masked


def test_when_the_username_is_not_sandbox_should_use_the_live_service(sandbox, monkeypatch):
    calls, _ = sandbox
    monkeypatch.setenv("AT_USERNAME", "wasac")
    monkeypatch.setenv("AT_SENDER_ID", "WASAC")
    sms.send_sms("+250788000111", "hi")
    assert calls[0]["url"] == sms.LIVE_URL and calls[0]["data"]["from"] == "WASAC"


@pytest.mark.parametrize("answer", [
    FakeResponse(201, {"SMSMessageData": {"Recipients": [{"statusCode": 403, "status": "InvalidPhoneNumber"}]}}),
    FakeResponse(401, {"error": "bad key"}),
    FakeResponse(201, None),
])
def test_when_africas_talking_refuses_should_return_false(sandbox, answer, caplog):
    _, answers = sandbox
    answers[0] = answer
    with caplog.at_level("INFO"):
        assert sms.send_sms("+250788000111", "x") is False
    assert KEY not in caplog.text


def test_when_the_network_fails_should_return_false(sandbox, monkeypatch):
    def fail(*a, **k):
        raise httpx.ConnectTimeout("slow")

    monkeypatch.setattr(sms.httpx, "post", fail)
    assert sms.send_sms("+250788000111", "x") is False


def test_when_a_code_is_requested_should_send_it_by_sms_and_not_log_it(db, anon_client, sandbox, caplog):
    calls, _ = sandbox
    add_household(db, "MTR-S", make_history([0.4] * 3))
    with caplog.at_level("INFO"):
        r = anon_client.post("/household/request-code", json={"phone": "0788000111"})
    assert r.status_code == 200 and r.json()["demo_code"] is None
    text = calls[0]["data"]["message"]
    code = text.split("code is ")[1][:6]
    assert code.isdigit() and code not in caplog.text
    assert anon_client.post("/household/verify", json={"phone": "0788000111", "code": code}).status_code == 200


def test_when_a_demo_household_requests_a_code_should_send_the_sms_and_show_the_code(db, anon_client, sandbox):
    calls, _ = sandbox
    add_household(db, "DEMO-MTR-001", make_history([0.4] * 3), phone="+250700000001")
    body = anon_client.post("/household/request-code", json={"phone": "0700000001"}).json()
    assert body["demo_code"] and body["demo_code"] in calls[0]["data"]["message"]


def test_when_the_sms_fails_should_return_503(db, anon_client, sandbox):
    _, answers = sandbox
    answers[0] = FakeResponse(500, None)
    add_household(db, "MTR-S", make_history([0.4] * 3))
    r = anon_client.post("/household/request-code", json={"phone": "0788000111"})
    assert r.status_code == 503
    assert db.query(HouseholdCode).count() == 1  # stored, but the household is told to try again


def test_when_settings_have_spaces_or_capitals_should_still_work(sandbox, monkeypatch):
    calls, _ = sandbox
    monkeypatch.setenv("AT_USERNAME", " Sandbox\n")
    monkeypatch.setenv("AT_API_KEY", f"  {KEY}\n")
    assert sms.send_sms("+250788000111", "hi") is True
    assert calls[0]["url"] == sms.SANDBOX_URL
    assert calls[0]["data"]["username"] == "sandbox" and calls[0]["headers"]["apiKey"] == KEY


def test_when_the_key_is_refused_should_log_africas_talkings_reason(sandbox, caplog):
    _, answers = sandbox
    answers[0] = FakeResponse(401, None, text="The supplied authentication is invalid")
    with caplog.at_level("INFO"):
        assert sms.send_sms("+250788000111", "x") is False
    assert "http=401 service=sandbox reason=The supplied authentication is invalid" in caplog.text
    assert KEY not in caplog.text


@pytest.fixture
def outbox(db, monkeypatch):
    """The sandbox outbox, writing to the test database."""
    monkeypatch.setenv("SMS_OUTBOX", "1")
    monkeypatch.setattr(sms, "_outbox_session", lambda: db)
    return db


def test_when_a_sandbox_sms_is_sent_should_keep_a_copy_for_admins(sandbox, outbox, db, as_admin):
    from app.models import SmsOutbox

    assert sms.send_sms("+250788000111", "Your bill is ready") is True
    row = db.query(SmsOutbox).one()
    assert (row.phone, row.message, row.status) == ("+250788000111", "Your bill is ready", "sent")
    listed = as_admin.get("/auth/sms-outbox").json()
    assert listed[0]["message"] == "Your bill is ready"


def test_when_the_live_service_is_used_should_keep_no_copy(sandbox, outbox, db, monkeypatch):
    from app.models import SmsOutbox

    monkeypatch.setenv("AT_USERNAME", "wasac")
    sms.send_sms("+250788000111", "hi")
    assert db.query(SmsOutbox).count() == 0


def test_when_the_outbox_is_full_should_keep_only_the_newest(sandbox, outbox, db, monkeypatch):
    from app.models import SmsOutbox

    monkeypatch.setenv("SMS_OUTBOX_KEEP", "2")
    for i in range(4):
        sms.send_sms("+250788000111", f"message {i}")
    assert [r.message for r in db.query(SmsOutbox).order_by(SmsOutbox.id)] == ["message 2", "message 3"]


def test_when_a_non_admin_opens_the_outbox_should_refuse_it(client):
    assert client.get("/auth/sms-outbox").status_code == 403
