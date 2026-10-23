"""The USSD menu (*xxx# on any phone, no internet), as Africa's Talking calls it.

Each step, Africa's Talking sends everything typed so far joined by "*" ("", "1", "1*00565846",
"1*00565846*1") and shows our answer: "CON ..." keeps the session open, "END ..." closes it.

    1  send a meter reading (8 digits, then confirm)     same rules as the app
    2  my latest bill
    3  pay my latest unpaid bill (MTN MoMo PIN prompt)
    9  English / Kinyarwanda (Kinyarwanda first)

Readings sent here have no photo: they are checked by the same rules as every reading
(app/anomaly/service.py) and the phone's SIM is the household's identity.
Kinyarwanda texts are drafts to be reviewed with the app's strings.
"""
from typing import Optional

from sqlalchemy.orm import Session

from app.anomaly.service import ReadingRefused, notify_household, submit_reading
from app.models import Bill, Customer, Meter
from app.services.payments import start_payment
from app.services.reading_window import PENDING, reading_block
from app.utils.meter_value import parse_meter_value
from app.utils.phone import normalize_phone

TEXT = {
    "rw": {
        "root": "WASAC: fagitire y'amazi\n1. Ohereza igipimo\n2. Fagitire yanjye\n3. Ishyura fagitire\n9. English",
        "unknown_phone": "Iyi nimero ntihuye na konti ya WASAC. Hamagara WASAC kuri 1580.",
        "ask_reading": "Andika imibare 8 iri kuri mubazi (5 z'umukara, 3 z'umutuku). Urugero: 00565846",
        "bad_reading": "Andika imibare 8 gusa, urugero 00565846. Ongera ugerageze.",
        "confirm": "Igipimo: {reading} m3\n1. Emeza\n2. Hagarika",
        "cancelled": "Byahagaritswe. Nta cyoherejwe.",
        "duplicate": "Iki gipimo cyoherejwe ubu. Reba fagitire zawe mbere yo kongera kucyohereza.",
        "pending": "Igipimo giheruka kiracyagenzurwa. Muzohereza ikindi nyuma y'icyemezo.",
        "too_soon": "Igipimo cy'uku kwezi cyakiriwe. Igikurikiraho ni guhera ku wa {date}.",
        "billed": "Murakoze. Igipimo: {reading} m3. Fagitire: RWF {amount}. Kanda 3 kuri menu kugira ngo wishyure.",
        "held": "Murakoze. Umukozi wa WASAC aragenzura iki gipimo mbere ya fagitire. Tuzabamenyesha kuri SMS.",
        "no_bill": "Nta fagitire mufite.",
        "bill": "Fagitire ya {month}: RWF {amount}, {status}.",
        "paid": "yishyuwe",
        "unpaid": "ntiyishyuwe",
        "nothing_to_pay": "Nta fagitire itarishyurwa.",
        "ask_pay": "Ishyura RWF {amount} kuri MoMo ({phone})?\n1. Yego\n2. Oya",
        "pay_prompt": "Emeza kwishyura kuri telefoni yawe ukoresheje umubare w'ibanga wa MoMo.",
        "pay_done": "Fagitire yishyuwe. Murakoze.",
        "pay_failed": "Kwishyura ntibyakunze. Nta mafaranga yakuweho. Ongera ugerageze.",
        "bad_choice": "Ihitamo ritaribyo. Ongera ugerageze.",
    },
    "en": {
        "root": "WASAC water billing\n1. Send a meter reading\n2. My bill\n3. Pay my bill\n9. Kinyarwanda",
        "unknown_phone": "This number is not linked to a WASAC account. Call WASAC on 1580.",
        "ask_reading": "Type the 8 numbers on your meter (5 on black, 3 on red). Example: 00565846",
        "bad_reading": "Type 8 numbers only, for example 00565846. Please try again.",
        "confirm": "Reading: {reading} m3\n1. Confirm\n2. Cancel",
        "cancelled": "Cancelled. Nothing was sent.",
        "duplicate": "This reading was just sent. Check your bill before sending it again.",
        "pending": "Your last reading is still being checked. You can send a new one after the decision.",
        "too_soon": "This month's reading is in. The next one opens on {date}.",
        "billed": "Thank you. Reading: {reading} m3. Bill: RWF {amount}. Choose 3 in the menu to pay.",
        "held": "Thank you. A WASAC officer is checking this reading before the bill. We will tell you by SMS.",
        "no_bill": "You have no bills yet.",
        "bill": "{month} bill: RWF {amount}, {status}.",
        "paid": "paid",
        "unpaid": "not paid",
        "nothing_to_pay": "You have no unpaid bill.",
        "ask_pay": "Pay RWF {amount} with MoMo ({phone})?\n1. Yes\n2. No",
        "pay_prompt": "Approve the payment on your phone with your MoMo PIN.",
        "pay_done": "Bill paid. Thank you.",
        "pay_failed": "The payment did not go through. Nothing was taken. Please try again.",
        "bad_choice": "That choice is not on the menu. Please try again.",
    },
}


def _con(text: str) -> str:
    return f"CON {text}"


def _end(text: str) -> str:
    return f"END {text}"


def parse_reading(typed: str) -> Optional[float]:
    """'00565846' (8 wheel digits) or '565.846' -> 565.846 m3; anything else -> None."""
    typed = typed.strip()
    if typed.isdigit() and len(typed) == 8:
        return int(typed) / 1000
    return parse_meter_value(typed) if "." in typed or "," in typed else None


def _latest_bill(db: Session, customer: Customer, unpaid_only: bool = False) -> Optional[Bill]:
    query = db.query(Bill).filter(Bill.customer_id == customer.customer_id)
    if unpaid_only:
        query = query.filter(Bill.payment_status != "paid")
    return query.order_by(Bill.created_at.desc()).first()


def handle(db: Session, phone_number: str, text: str) -> str:
    parts = [p for p in (text or "").split("*")] if text else []
    lang = "rw"
    while parts and parts[0] == "9":  # language switch, any number of times
        lang = "en" if lang == "rw" else "rw"
        parts.pop(0)
    t = TEXT[lang]
    if not parts:
        return _con(t["root"])

    phone = normalize_phone(phone_number) or phone_number
    customer = db.query(Customer).filter(Customer.phone == phone).order_by(Customer.customer_id).first()
    if not customer:
        return _end(t["unknown_phone"])
    choice, rest = parts[0], parts[1:]

    if choice == "1":
        meter = db.query(Meter).filter(Meter.meter_id == customer.meter_id).first()
        block = reading_block(db, meter) if meter else None
        if block:
            return _end(t["pending"] if block.reason == PENDING else t["too_soon"].format(date=f"{block.opens_on:%d/%m/%Y}"))
        if not rest:
            return _con(t["ask_reading"])
        reading = parse_reading(rest[0])
        if reading is None:
            return _end(t["bad_reading"])
        if len(rest) == 1:
            return _con(t["confirm"].format(reading=f"{reading:.3f}"))
        if rest[1] != "1":
            return _end(t["cancelled"])
        try:
            sub = submit_reading(db, meter, customer.customer_id, reading, method="ussd", household=True)
        except ReadingRefused as refused:
            # Sent from another phone or the app while this session was open, or sent twice.
            if refused.block is None:
                return _end(t["duplicate"])
            return _end(t["pending"] if refused.block.reason == PENDING
                        else t["too_soon"].format(date=f"{refused.block.opens_on:%d/%m/%Y}"))
        notify_household(db, sub.anomaly)
        if sub.bill is None:
            return _end(t["held"])
        return _end(t["billed"].format(reading=f"{reading:.3f}", amount=f"{sub.bill.amount_due:,.0f}"))

    if choice == "2":
        bill = _latest_bill(db, customer)
        if not bill:
            return _end(t["no_bill"])
        status = t["paid"] if bill.payment_status == "paid" else t["unpaid"]
        return _end(t["bill"].format(month=f"{bill.created_at:%m/%Y}", amount=f"{bill.amount_due:,.0f}", status=status))

    if choice == "3":
        bill = _latest_bill(db, customer, unpaid_only=True)
        if not bill:
            return _end(t["nothing_to_pay"])
        if not rest:
            return _con(t["ask_pay"].format(amount=f"{bill.amount_due:,.0f}", phone=customer.phone))
        if rest[0] != "1":
            return _end(t["cancelled"])
        payment = start_payment(db, bill, customer.phone)
        if payment.status == "successful":
            return _end(t["pay_done"])
        if payment.status == "failed":
            return _end(t["pay_failed"])
        return _end(t["pay_prompt"])

    return _end(t["bad_choice"])
