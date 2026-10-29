"""Staff add, edit and upload households (app/services/households.py, app/api/routes/billing.py)."""
import pytest

from app.models import Customer, Meter, Reading, StaffAction
from support.clients import signed_in_client
from support.factories import add_household, add_officer, make_history

NEW = {"name": "Mukamana Alice", "phone": "0788 555 123", "meter_id": "kgl-30001", "sector": "Remera",
       "serial_number": "itr24123456", "first_reading": "120.5"}
CSV = (
    "Name,Phone,Meter number,Sector,Serial number,First reading\n"
    "Mukamana Alice,0788555123,KGL-30001,Remera,ITR24123456,120.5\n"
    "Habimana Eric,+250 722 000 444,KGL-30002,Gisozi,,\n"
)


@pytest.fixture
def supervisor(db):
    add_officer(db, username="sup1", role="supervisor")
    fastapi_app, c = signed_in_client(db, "sup1")
    yield c
    fastapi_app.dependency_overrides.clear()


def test_when_staff_add_a_household_should_create_it_so_the_phone_can_sign_in(db, client, anon_client):
    r = client.post("/customers", json=NEW)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["meter_id"] == "KGL-30001" and body["phone"] == "+250788555123"
    assert body["serial_number"] == "ITR24123456" and body["last_reading"] == 120.5 and not body["is_demo"]
    assert db.get(Meter, "KGL-30001").customer_id == body["customer_id"]
    # The first reading is a starting point, not this period's reading: the household can read now.
    assert db.query(Reading).filter(Reading.meter_id == "KGL-30001").one().submission_method == "correction"
    assert body["next_reading_from"] is None
    assert db.query(StaffAction).filter(StaffAction.action == "household_added").one().target == "KGL-30001"

    sent = anon_client.post("/household/request-code", json={"phone": "0788555123"})
    assert sent.status_code == 200 and sent.json().get("demo_code") is None  # real households: SMS only


def test_when_the_meter_is_already_registered_should_refuse_a_second_household(client):
    assert client.post("/customers", json=NEW).status_code == 201
    r = client.post("/customers", json={**NEW, "phone": "0788000999"})
    assert r.status_code == 409 and "already registered" in r.json()["detail"]


def test_when_the_fields_are_wrong_should_say_what_to_fix(client):
    r = client.post("/customers", json={**NEW, "phone": "12345", "meter_id": "DEMO-X1", "first_reading": "abc"})
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert "Rwandan mobile" in detail and "DEMO-" in detail and "first reading" in detail


def test_when_a_serial_number_is_on_another_meter_should_refuse_it(client):
    client.post("/customers", json=NEW)
    r = client.post("/customers", json={**NEW, "meter_id": "KGL-30009"})
    assert r.status_code == 409 and "Serial number" in r.json()["detail"]


def test_when_staff_edit_a_household_should_change_its_details_and_log_what_changed(db, client):
    customer_id = add_household(db, "MTR-E", make_history([0.4] * 3))
    r = client.patch(f"/customers/{customer_id}", json={"name": "Test", "phone": "0788111222", "sector": "Kicukiro",
                                                        "serial_number": "SN-77"})
    assert r.status_code == 200, r.text
    assert r.json()["phone"] == "+250788111222" and r.json()["serial_number"] == "SN-77"
    action = db.query(StaffAction).filter(StaffAction.action == "household_updated").one()
    assert action.target == "MTR-E" and action.detail == "phone, sector, serial"


def test_when_households_are_not_signed_in_should_refuse_to_add_or_edit(db, household_client):
    customer_id = add_household(db, "MTR-H", make_history([0.4] * 3))
    assert household_client.post("/customers", json=NEW).status_code in (401, 403)
    assert household_client.patch(f"/customers/{customer_id}", json={"name": "X Y", "phone": "0788111222",
                                                                       "sector": "Kicukiro"}).status_code in (401, 403)


def test_when_a_supervisor_previews_a_csv_should_save_nothing(db, supervisor):
    r = supervisor.post("/customers/import", json={"csv": CSV})
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["new"], body["error"], body["applied"]) == (2, 0, False)
    assert db.query(Customer).count() == 0


def test_when_a_supervisor_confirms_a_csv_should_add_and_update_households(db, supervisor):
    customer_id = add_household(db, "KGL-30002", make_history([0.4] * 3))
    body = supervisor.post("/customers/import", json={"csv": CSV, "apply": True}).json()
    assert (body["new"], body["update"], body["applied"]) == (1, 1, True)
    assert body["rows"][1]["changes"] == ["name", "phone", "sector"]
    assert db.get(Customer, customer_id).name == "Habimana Eric"
    assert db.get(Meter, "KGL-30001").serial_number == "ITR24123456"
    action = db.query(StaffAction).filter(StaffAction.action == "households_imported").one()
    assert action.detail == "1 new, 1 updated"


def test_when_any_row_is_wrong_should_list_it_and_save_nothing(db, supervisor):
    bad = CSV + "No Phone,,KGL-30003,Kanombe,,\nMukamana Alice,0788555123,KGL-30001,Remera,,\n"
    body = supervisor.post("/customers/import", json={"csv": bad, "apply": True}).json()
    assert body["applied"] is False and body["error"] == 2
    errors = {row["line"]: row["errors"] for row in body["rows"] if row["errors"]}
    assert errors == {4: ["phone"], 5: ["dup_meter:2"]}
    assert db.query(Customer).count() == 0


def test_when_an_upload_names_a_demo_household_should_refuse_to_change_it(db, supervisor):
    db.add(Meter(meter_id="KGL-20001", customer_id="DEMO-CUST-001"))
    db.add(Customer(customer_id="DEMO-CUST-001", name="DEMO Household 001", phone="+250700000001",
                    meter_id="KGL-20001", sector="Remera"))
    db.commit()
    body = supervisor.post("/customers/import", json={"csv": "name,phone,meter,sector\nX Y,0788000111,KGL-20001,Remera\n"}).json()
    assert body["error"] == 1 and body["rows"][0]["errors"] == ["demo_household"]


def test_when_the_file_misses_a_column_should_say_which(supervisor):
    r = supervisor.post("/customers/import", json={"csv": "name,phone\nA B,0788000111\n"})
    assert r.status_code == 422 and "meter_id" in r.json()["detail"] and "sector" in r.json()["detail"]


def test_when_the_file_uses_semicolons_should_still_read_it(supervisor):
    body = supervisor.post("/customers/import", json={"csv": "name;phone;meter_no;sector\nA B;0788000111;KGL-1;Remera\n"}).json()
    assert body["new"] == 1


def test_when_an_officer_uploads_a_list_should_refuse_it(client):
    assert client.post("/customers/import", json={"csv": CSV}).status_code == 403
