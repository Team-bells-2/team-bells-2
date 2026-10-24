import re
from collections.abc import Iterable
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from app.ai.schemas import Interpretation
from app.customers.models import Customer
from app.ledger.models import Entry
from app.ledger.schemas import EntryOut, ExtractedEntry
from app.shared.naira import parse_naira_amount  # noqa: F401  (FR-S4 parser; re-exported for callers)

NOT_UNDERSTOOD_MESSAGE = "Sorry, I didn't catch that. Can you say it again?"
FALLBACK_MESSAGE = "I can record sales, credit sales, payments and expenses. Tell me what you sold, collected or spent."
# Added to the reply when the assistant was down and the built-in rules read the message (NFR-3).
RULES_NOTE = "(The assistant is busy, so I read this with basic rules. Check it is right.)"
NOT_SAVED_MESSAGE = "Okay, I didn't save it. Tell me again what happened."
WHICH_CUSTOMER_QUESTION = "Which customer is this for?"

# Answers to "Do you mean ...?" and "Just to confirm ...?", detected in code (BR-L6).
_YES_PATTERN = re.compile(r"^\s*(yes|yeah|yep|correct|exactly|na\s+(she|he|am|her|him)|e\s+be\s+so|ehen|ehn|ok)\b")
_NO_PATTERN = re.compile(r"^\s*(no|nope|not\s+(her|him)|no\s+be\s+(she|he|am))\b")

# Pending-clarification bookkeeping kept inside partial_entry, never part of the entry itself.
PENDING_TEXTS = "raw_texts"
PENDING_KIND = "_kind"  # "missing", "confirm_entry", "confirm_item" or "confirm_customer"
PENDING_CANDIDATE = "_candidate"
PENDING_MENTION = "_mention"
PENDING_ITEM_CHECKED = "_item_checked"  # the item was already matched against inventory; don't ask again
_PENDING_KEYS = {PENDING_TEXTS, PENDING_KIND, PENDING_CANDIDATE, PENDING_MENTION, PENDING_ITEM_CHECKED}
CONFIRM_KINDS = {"confirm_entry", "confirm_item", "confirm_customer"}
STOCK_TYPES = {"sale", "credit_sale", "expense"}


def is_yes(text: str) -> bool:
    return bool(_YES_PATTERN.search(text.casefold()))


def is_no(text: str) -> bool:
    return bool(_NO_PATTERN.search(text.casefold()))


def entry_fields(partial: dict[str, Any]) -> dict[str, Any]:
    """The entry's own fields from a pending partial entry, without the bookkeeping keys."""
    return {key: value for key, value in partial.items() if key not in _PENDING_KEYS}


def customers_named_in(text: str, aliases: Iterable[tuple[str, Customer]]) -> list[Customer]:
    """Customers with an alias appearing in the text as whole words, ignoring case (BR-L5)."""
    lowered = text.casefold()
    found: dict[int, Customer] = {}
    for alias, customer in aliases:
        if re.search(rf"\b{re.escape(alias.casefold())}\b", lowered):
            found[customer.id] = customer
    return list(found.values())


def starts_over(text: str, new: ExtractedEntry, pending_fields: dict[str, Any]) -> bool:
    """A different, complete entry sent while a question is pending replaces the pending entry (BR-L2).
    A yes/no answer or a short reply never does."""
    if is_yes(text) or is_no(text) or len(text.split()) < 3:
        return False
    if missing_fields(new.model_dump(mode="json", exclude_none=True)) or not (new.item or new.customer):
        return False

    def differs(field: str) -> bool:
        value, pending_value = getattr(new, field), pending_fields.get(field)
        return bool(value and pending_value and str(value).casefold() != str(pending_value).casefold())

    return new.type != pending_fields.get("type") or differs("item") or differs("customer")

_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def resolve_due_date(text: str, today: date) -> date | None:
    """A relative due phrase to a date, in code, never by the model (FR-S12, BR-A2):
    "tomorrow" / "tmrw" +1, "next tomorrow" +2, "next week" +7, a weekday name -> its next
    occurrence (the same weekday as today -> a week ahead). None when not recognised."""
    lowered = text.casefold()
    if re.search(r"\bnext\s+tomorrow\b", lowered):
        return today + timedelta(days=2)
    if re.search(r"\b(tomorrow|tmrw)\b", lowered):
        return today + timedelta(days=1)
    if re.search(r"\bnext\s+week\b", lowered):
        return today + timedelta(days=7)
    for index, day in enumerate(_WEEKDAYS):
        if re.search(rf"\b{day}\b", lowered):
            return today + timedelta(days=(index - today.weekday()) % 7 or 7)
    return None


def to_extracted(interpretation: Interpretation, today: date) -> ExtractedEntry:
    """Interpretation to ledger fields; the amount and the due date come from code parsing the
    phrases the model quoted, against the trader's current date."""
    amount = parse_naira_amount(interpretation.amount_text) if interpretation.amount_text else None
    due_date = resolve_due_date(interpretation.due_text, today) if interpretation.due_text else None
    return ExtractedEntry(
        type=interpretation.type,
        item=interpretation.item or None,
        quantity=interpretation.quantity,
        unit=interpretation.unit or None,
        amount_ngn=amount,
        customer=interpretation.customer or None,
        due_date=due_date,
        confidence=interpretation.confidence,
    )


def is_low_confidence(confidence: float | None, threshold: float) -> bool:
    return confidence is not None and confidence < threshold


def confirmation_question(fields: dict[str, Any]) -> str:
    """Asked when a complete entry was read with low confidence (FR-S5)."""
    entry_type = _TYPE_LABELS.get(str(fields.get("type")), "entry")
    item = f" of {fields['item']}" if fields.get("item") else ""
    customer = f" for {fields['customer']}" if fields.get("customer") else ""
    amount = Decimal(str(fields.get("amount_ngn") or 0))
    return f"Just to confirm: {entry_type}{item}{customer}, {format_naira(amount)}?"


CUSTOMER_TYPES = {"credit_sale", "payment_received"}
SALE_TYPES = {"sale", "credit_sale"}

_QUESTIONS = {
    "type": "Was this a sale, a credit sale, a payment or an expense?",
    "amount_ngn": "How much was it?",
    "customer": WHICH_CUSTOMER_QUESTION,
}

_TYPE_LABELS = {
    "sale": "sale",
    "credit_sale": "credit sale",
    "payment_received": "payment",
    "expense": "expense",
}


def merge_partial(partial: dict[str, Any], extracted: ExtractedEntry) -> dict[str, Any]:
    """Fill the pending partial entry with whatever the new message supplies."""
    return {**entry_fields(partial), **extracted.model_dump(mode="json", exclude_none=True)}


def missing_fields(fields: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    if fields.get("type") is None:
        missing.append("type")
    if fields.get("amount_ngn") is None:
        missing.append("amount_ngn")
    if fields.get("type") in CUSTOMER_TYPES and not fields.get("customer"):
        missing.append("customer")
    return missing


def missing_question(fields: dict[str, Any]) -> str:
    """One question for the first missing field, using what is already known (BR-L3), e.g.
    "How much did you collect for the 2.5 bags?" (FR-S5 acceptance)."""
    first = missing_fields(fields)[0]
    quantity, unit = fields.get("quantity"), fields.get("unit")
    if first == "amount_ngn" and quantity is not None and unit:
        amount = Decimal(str(quantity))
        verb = "pay" if fields.get("type") == "expense" else "collect"
        return f"How much did you {verb} for the {amount.normalize():f} {plural_unit(unit, amount)}?"
    return _QUESTIONS[first]


def plural_unit(unit: str, quantity: Decimal) -> str:
    return unit if quantity <= 1 or unit.endswith("s") or unit.casefold() == "kg" else f"{unit}s"


def ambiguous_customer_question(names: list[str]) -> str:
    return f"Do you mean {' or '.join(sorted(names))}?"


def stock_effect(entry_type: str, quantity: Decimal | None) -> tuple[Decimal, str] | None:
    """Sales take stock out; an expense on a stocked item is a restock (FR-S25, S26)."""
    if quantity is None:
        return None
    if entry_type in SALE_TYPES:
        return -quantity, "sale"
    if entry_type == "expense":
        return quantity, "restock"
    return None


def format_naira(amount: Decimal) -> str:
    return f"₦{amount:,.0f}" if amount == amount.to_integral_value() else f"₦{amount:,.2f}"


def build_confirmation(entry: Entry, customer_name: str | None, corrected: bool) -> str:
    """One line built from saved fields only, never from model text (FR-S7)."""
    parts = [_TYPE_LABELS[entry.type]]
    if entry.item:
        quantity = f"{entry.quantity.normalize():f} " if entry.quantity is not None else ""
        unit = f"{entry.unit} " if entry.unit else ""
        parts.append(f"of {quantity}{unit}{entry.item}")
    if customer_name:
        parts.append(f"{'from' if entry.type == 'payment_received' else 'to'} {customer_name}")
    parts.append(f"for {format_naira(entry.amount_ngn)}")
    if entry.due_date:
        parts.append(f"due {entry.due_date:%a %d %b}")  # "due Fri 30 Oct" (BR-L12)
    prefix = "Updated" if corrected else "Saved"
    return f"{prefix}: {' '.join(parts)}."


def entry_snapshot(entry: Entry, customer_name: str | None) -> dict[str, Any]:
    """JSON-safe copy of the editable fields, for the correction audit trail."""
    return {
        "type": entry.type,
        "item": entry.item,
        "quantity": str(entry.quantity) if entry.quantity is not None else None,
        "unit": entry.unit,
        "amount_ngn": str(entry.amount_ngn),
        "customer": customer_name,
        "due_date": entry.due_date.isoformat() if entry.due_date else None,
        "confidence": entry.confidence,
    }


def to_entry_out(entry: Entry, customer_name: str | None) -> EntryOut:
    return EntryOut(
        id=entry.id,
        type=entry.type,  # pyright: ignore[reportArgumentType]  (DB check constraint guarantees the literal)
        item=entry.item,
        quantity=entry.quantity,
        unit=entry.unit,
        amount_ngn=entry.amount_ngn,
        customer=customer_name,
        due_date=entry.due_date,
        confidence=entry.confidence,
        status=entry.status,
        stock_warning=entry.stock_warning,  # pyright: ignore[reportArgumentType]  (only the ledger writes it)
        raw_text=entry.raw_text,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )
