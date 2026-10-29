"""Staff add households, edit them, or upload WASAC's customer list as a CSV.

Households cannot create accounts themselves: a phone number can sign in only once staff have
linked it to a meter here (or the list was uploaded), so nobody can claim someone else's meter.

    check_fields()      one household's fields, cleaned; or the reasons they are wrong
    add_household()     a new household and its meter (optionally with a first reading)
    edit_household()    name, phone, sector, serial number (the meter number never changes)
    import_csv()        preview a CSV upload (new / updated / unchanged / errors), or apply it

DEMO- households are made only by scripts/demo/generate_demo_households.py: staff cannot create
one here, and an upload cannot change one.
"""
import csv
import io
import re
import secrets
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models import Customer, Meter
from app.services.meter_correction import MAX_READING_M3, correct_meter
from app.utils.phone import normalize_phone

DEMO_PREFIX = "DEMO-"
MAX_IMPORT_ROWS = 5000
CODE = re.compile(r"^[A-Z0-9][A-Z0-9/-]{2,29}$")       # meter and customer numbers
SERIAL = re.compile(r"^[A-Z0-9][A-Z0-9/-]{2,39}$")

# CSV header -> field. Several spellings, so an export from WASAC's system needs little editing.
HEADERS = {
    "name": "name", "customer_name": "name", "full_name": "name",
    "phone": "phone", "phone_number": "phone", "mobile": "phone",
    "meter": "meter_id", "meter_id": "meter_id", "meter_number": "meter_id", "meter_no": "meter_id",
    "sector": "sector",
    "serial": "serial_number", "serial_number": "serial_number", "meter_serial": "serial_number",
    "first_reading": "first_reading", "reading": "first_reading", "reading_m3": "first_reading",
    "customer_number": "customer_id", "customer_id": "customer_id", "account_number": "customer_id",
}
REQUIRED = ("name", "phone", "meter_id", "sector")


class HouseholdError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


@dataclass
class Fields:
    name: str
    phone: str
    meter_id: str
    sector: str
    serial_number: Optional[str] = None
    first_reading: Optional[float] = None
    customer_id: Optional[str] = None


# What each error code means. The API returns the codes; the staff dashboard shows them in the
# person's language (frontend staff.household.err.*). The English is for API callers and logs.
MESSAGES = {
    "name": "Enter the household's name (2 to 120 characters).",
    "phone": "Enter a Rwandan mobile number, for example 078 123 4567.",
    "sector": "Enter the sector, for example Kacyiru.",
    "serial": "The serial number has letters, numbers, - or / only.",
    "meter": "Enter the meter number (3 to 30 letters, numbers, - or /).",
    "meter_demo": "Meter numbers starting with DEMO- are kept for test households.",
    "reading": "The first reading is a number of m3 between 0 and 99999.999.",
    "customer": "The customer number has letters, numbers, - or / only, and does not start with DEMO-.",
}


def describe(errors: List[str]) -> str:
    return " ".join(MESSAGES.get(code, code) for code in errors)


def _code(raw: Optional[str]) -> str:
    return re.sub(r"\s+", "", raw or "").upper()


def check_fields(raw: Dict[str, Optional[str]], *, new: bool = True) -> "tuple[Optional[Fields], List[str]]":
    """Clean one household's fields, or return error codes (MESSAGES). `new=False` (an edit)
    skips the meter number, first reading and customer number."""
    errors: List[str] = []
    name = " ".join((raw.get("name") or "").split())
    if not 2 <= len(name) <= 120:
        errors.append("name")
    phone = normalize_phone(raw.get("phone") or "")
    if not phone:
        errors.append("phone")
    sector = " ".join((raw.get("sector") or "").split())
    if not 2 <= len(sector) <= 60:
        errors.append("sector")
    serial = _code(raw.get("serial_number")) or None
    if serial and not SERIAL.match(serial):
        errors.append("serial")

    meter_id, reading, customer_id = "", None, None
    if new:
        meter_id = _code(raw.get("meter_id"))
        if not CODE.match(meter_id):
            errors.append("meter")
        elif meter_id.startswith(DEMO_PREFIX):
            errors.append("meter_demo")
        text = (raw.get("first_reading") or "").strip().replace(",", ".")
        if text:
            try:
                reading = round(float(text), 3)
            except ValueError:
                reading = -1.0
            if not 0 <= reading <= MAX_READING_M3:
                errors.append("reading")
        customer_id = _code(raw.get("customer_id")) or None
        if customer_id and (not CODE.match(customer_id) or customer_id.startswith(DEMO_PREFIX)):
            errors.append("customer")
    if errors:
        return None, errors
    return Fields(name=name, phone=phone, meter_id=meter_id, sector=sector, serial_number=serial,
                  first_reading=reading, customer_id=customer_id), []


def _serial_taken(db: Session, serial: Optional[str], meter_id: str) -> bool:
    if not serial:
        return False
    return db.query(Meter.meter_id).filter(Meter.serial_number == serial, Meter.meter_id != meter_id).first() is not None


def _new_customer_id(db: Session) -> str:
    while True:
        candidate = f"C-{secrets.randbelow(10**8):08d}"
        if not db.get(Customer, candidate):
            return candidate


def add_household(db: Session, f: Fields) -> Customer:
    """A new household and its meter. Commits nothing."""
    if db.get(Meter, f.meter_id):
        raise HouseholdError(409, f"Meter {f.meter_id} is already registered.")
    if f.customer_id and db.get(Customer, f.customer_id):
        raise HouseholdError(409, f"Customer number {f.customer_id} is already registered.")
    if _serial_taken(db, f.serial_number, f.meter_id):
        raise HouseholdError(409, f"Serial number {f.serial_number} is already on another meter.")
    customer_id = f.customer_id or _new_customer_id(db)
    # meters and customers reference each other, so link them after both rows exist.
    meter = Meter(meter_id=f.meter_id, last_reading=0.0, serial_number=f.serial_number)
    db.add(meter)
    db.flush()
    customer = Customer(customer_id=customer_id, name=f.name, phone=f.phone, meter_id=f.meter_id, sector=f.sector)
    db.add(customer)
    db.flush()
    meter.customer_id = customer_id
    if f.first_reading is not None:
        correct_meter(db, meter, f.first_reading)  # the starting point the first photo is compared with
    return customer


def edit_household(db: Session, customer: Customer, f: Fields) -> "List[str]":
    """Change name, phone, sector and serial number. Returns what changed. Commits nothing."""
    meter = db.get(Meter, customer.meter_id)
    if _serial_taken(db, f.serial_number, customer.meter_id):
        raise HouseholdError(409, f"Serial number {f.serial_number} is already on another meter.")
    changed = []
    for label, obj, attr, value in (
        ("name", customer, "name", f.name), ("phone", customer, "phone", f.phone),
        ("sector", customer, "sector", f.sector), ("serial", meter, "serial_number", f.serial_number),
    ):
        if obj is not None and getattr(obj, attr) != value:
            setattr(obj, attr, value)
            changed.append(label)
    return changed


@dataclass
class ImportRow:
    line: int
    meter_id: str
    name: str
    action: str                      # "new", "update", "unchanged" or "error"
    errors: List[str] = field(default_factory=list)   # codes; "dup_meter:5" = same meter as line 5
    changes: List[str] = field(default_factory=list)


@dataclass
class ImportResult:
    rows: List[ImportRow]
    applied: bool = False

    def count(self, action: str) -> int:
        return sum(1 for r in self.rows if r.action == action)


def _read_csv(text: str) -> "tuple[List[Dict[str, str]], List[str]]":
    text = text.lstrip("﻿")  # Excel's byte-order mark
    try:
        dialect = csv.Sniffer().sniff(text[:2048], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(io.StringIO(text), dialect)
    header = next(reader, None)
    if not header:
        raise HouseholdError(422, "The file is empty.")
    columns = [HEADERS.get(re.sub(r"[\s.]+", "_", h.strip().lower())) for h in header]
    missing = [c for c in REQUIRED if c not in columns]
    if missing:
        raise HouseholdError(422, "The file needs the columns name, phone, meter_number and sector. "
                                  f"Missing: {', '.join(missing)}.")
    rows = []
    for values in reader:
        if not any(v.strip() for v in values):
            continue
        rows.append({col: v for col, v in zip(columns, values) if col})
        if len(rows) > MAX_IMPORT_ROWS:
            raise HouseholdError(422, f"Upload at most {MAX_IMPORT_ROWS} households at a time.")
    if not rows:
        raise HouseholdError(422, "The file has no households under the column names.")
    return rows, [c for c in columns if c]


def import_csv(db: Session, text: str, apply: bool = False) -> ImportResult:
    """Check every row; with apply=True and no errors, save them all. Commits nothing.
    A row whose meter is already registered updates that household (not its reading)."""
    raw_rows, _ = _read_csv(text)
    rows: List[ImportRow] = []
    plans = []
    seen_meters: Dict[str, int] = {}
    seen_serials: Dict[str, int] = {}
    seen_customers: Dict[str, int] = {}
    for line, raw in enumerate(raw_rows, start=2):  # line 1 is the header
        meter_id = _code(raw.get("meter_id"))
        f, errors = check_fields(raw)
        row = ImportRow(line=line, meter_id=meter_id, name=(raw.get("name") or "").strip()[:120], action="error",
                        errors=errors)
        rows.append(row)
        if f is None:
            continue
        if f.meter_id in seen_meters:
            row.errors.append(f"dup_meter:{seen_meters[f.meter_id]}")
        seen_meters.setdefault(f.meter_id, line)
        if f.serial_number:
            if f.serial_number in seen_serials:
                row.errors.append(f"dup_serial:{seen_serials[f.serial_number]}")
            seen_serials.setdefault(f.serial_number, line)
        if f.customer_id:
            if f.customer_id in seen_customers:
                row.errors.append(f"dup_customer:{seen_customers[f.customer_id]}")
            seen_customers.setdefault(f.customer_id, line)
        if _serial_taken(db, f.serial_number, f.meter_id):
            row.errors.append("serial_taken")

        meter = db.get(Meter, f.meter_id)
        customer = db.query(Customer).filter(Customer.meter_id == f.meter_id).first() if meter else None
        if meter and not customer:
            row.errors.append("meter_alone")
        elif customer and customer.customer_id.startswith(DEMO_PREFIX):
            row.errors.append("demo_household")
        elif customer and f.customer_id and f.customer_id != customer.customer_id:
            row.errors.append(f"other_customer:{customer.customer_id}")
        elif not customer and f.customer_id and db.get(Customer, f.customer_id):
            row.errors.append("customer_taken")
        if row.errors:
            continue
        if customer:
            row.changes = [label for label, now, new in (
                ("name", customer.name, f.name), ("phone", customer.phone, f.phone),
                ("sector", customer.sector, f.sector), ("serial", meter.serial_number, f.serial_number),
            ) if now != new]
            row.action = "update" if row.changes else "unchanged"
        else:
            row.action = "new"
        plans.append((row, f, customer))

    result = ImportResult(rows=rows)
    if apply and not any(r.action == "error" for r in rows):
        for row, f, customer in plans:
            if row.action == "new":
                add_household(db, f)
            elif row.action == "update":
                edit_household(db, customer, f)
        result.applied = True
    return result
