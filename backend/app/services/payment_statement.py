"""A list of payments WASAC received, which an officer's confirmation is checked against.

The project has no access to WASAC's real MoMo or bank accounts, so this list is synthetic test
data, uploaded as a CSV by a supervisor. Once a list exists, a MoMo Pay payment can only be confirmed
if its transaction ID is on it with the same amount. With no list, the officer's own check stands.
"""
import csv
import io
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models import PaymentStatementEntry

COLUMNS = ("transaction_id", "amount", "reference")
MATCHED = "matched"
NOT_FOUND = "not_found"
AMOUNT_DIFFERS = "amount_differs"
ROUNDING = 1.0  # MoMo takes whole francs


class StatementError(ValueError):
    pass


@dataclass
class StatementResult:
    added: int = 0
    updated: int = 0
    errors: List[str] = field(default_factory=list)  # "<line>:<code>"


def normalise(transaction_id: str) -> str:
    return transaction_id.strip().upper()


def parse_statement(text: str) -> Tuple[List[Tuple[str, float, Optional[str]]], List[str]]:
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    headers = [(h or "").strip().lower() for h in reader.fieldnames or []]
    if not {"transaction_id", "amount"} <= set(headers):
        raise StatementError("The file needs transaction_id and amount columns.")
    reader.fieldnames = headers
    rows: List[Tuple[str, float, Optional[str]]] = []
    errors: List[str] = []
    seen = set()
    for line, row in enumerate(reader, start=2):
        transaction_id = normalise(row.get("transaction_id") or "")
        try:
            amount = float((row.get("amount") or "").replace(",", ""))
        except ValueError:
            amount = -1.0
        if not transaction_id or len(transaction_id) > 64:
            errors.append(f"{line}:transaction_id")
        elif transaction_id in seen:
            errors.append(f"{line}:duplicate")
        elif not 0 < amount < 1e12:
            errors.append(f"{line}:amount")
        else:
            seen.add(transaction_id)
            rows.append((transaction_id, amount, (row.get("reference") or "").strip()[:64] or None))
    return rows, errors


def import_statement(db: Session, text: str, staff: str) -> StatementResult:
    """All or nothing: a file with any mistake saves no row. Does not commit."""
    rows, errors = parse_statement(text)
    result = StatementResult(errors=errors)
    if errors:
        return result
    for transaction_id, amount, reference in rows:
        entry = db.get(PaymentStatementEntry, transaction_id)
        if entry:
            entry.amount, entry.reference, entry.uploaded_by = amount, reference, staff
            result.updated += 1
        else:
            db.add(PaymentStatementEntry(transaction_id=transaction_id, amount=amount, reference=reference, uploaded_by=staff))
            result.added += 1
    return result


def statement_status(db: Session, transaction_id: Optional[str], amount: float) -> Optional[str]:
    """None when no list has been uploaded."""
    if db.query(PaymentStatementEntry.transaction_id).first() is None:
        return None
    entry = db.get(PaymentStatementEntry, normalise(transaction_id or ""))
    if entry is None:
        return NOT_FOUND
    return MATCHED if abs(entry.amount - amount) < ROUNDING else AMOUNT_DIFFERS
