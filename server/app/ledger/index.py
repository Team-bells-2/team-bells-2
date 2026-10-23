from __future__ import annotations

import base64
import binascii
import logging
import re
import time
from datetime import UTC, date, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.customers.models import Customer, CustomerAlias
from app.inventory.models import InventoryItem, StockMovement
from app.ledger.models import Entry, EntryEdit, PendingClarification, ProcessedMessage
from app.ledger.schemas import EntriesResponse, EntryData, EntryResponse, MessageRequest, MessageResponse
from app.onboarding.models import Trader
from app.shared.Infrastructure.db.session import get_db
from app.shared.Infrastructure.llm.index import (
    extract_correction,
    extract_entry,
    is_correction,
    match_customer,
    normalize_unit,
)
from app.shared.Infrastructure.SST.index import transcribe
from app.shared.auth import get_current_trader

router = APIRouter(tags=["ledger"])
logger = logging.getLogger("oja.messages")

YES_PATTERN = re.compile(r"^\s*(yes|yeah|yep|correct|exactly|na\s+(she|he|am|her|him)|e\s+be\s+so|ehen|ehn|ok)\b")
NO_PATTERN = re.compile(r"^\s*(no|nope|not\s+(her|him)|no\s+be\s+(she|he|am))\b")


def _customer_list(db: Session, trader_id: int) -> list[dict[str, Any]]:
    customers = db.scalars(select(Customer).where(Customer.trader_id == trader_id).order_by(Customer.canonical_name)).all()
    aliases = db.execute(select(CustomerAlias.customer_id, CustomerAlias.alias).join(Customer).where(Customer.trader_id == trader_id)).all()
    return [
        {"name": customer.canonical_name, "aliases": [alias for customer_id, alias in aliases if customer_id == customer.id and alias != customer.canonical_name]}
        for customer in customers
    ]


def _customer_by_name(db: Session, trader_id: int, name: str) -> Customer | None:
    return db.scalar(select(Customer).where(Customer.trader_id == trader_id, func.lower(Customer.canonical_name) == name.strip().lower()))


def _add_alias(db: Session, customer: Customer, alias: str | None) -> None:
    alias = " ".join((alias or "").split())
    if not alias:
        return
    exists = db.scalar(select(CustomerAlias).where(CustomerAlias.customer_id == customer.id, func.lower(CustomerAlias.alias) == alias.lower()))
    if not exists:
        db.add(CustomerAlias(customer_id=customer.id, alias=alias))


def _create_customer(db: Session, trader_id: int, name: str) -> Customer:
    canonical = " ".join(name.split()).strip()
    customer = Customer(trader_id=trader_id, canonical_name=canonical)
    db.add(customer)
    db.flush()
    _add_alias(db, customer, canonical)
    return customer


def _alias_matches(db: Session, trader_id: int, text: str) -> list[Customer]:
    rows = db.execute(select(CustomerAlias.alias, Customer).join(Customer, Customer.id == CustomerAlias.customer_id).where(Customer.trader_id == trader_id)).all()
    lowered = text.casefold()
    unique = {customer.id: customer for alias, customer in rows if re.search(rf"\b{re.escape(alias.casefold())}\b", lowered)}
    return list(unique.values())


def _resolve_customer(db: Session, trader_id: int, text: str, mention: str | None) -> tuple[str, Any]:
    """FR-S9: alias table first, then the model against the existing list. Returns (status, value)."""
    matches = _alias_matches(db, trader_id, text)
    if len(matches) == 1:
        return "ok", matches[0]
    if len(matches) > 1:
        if mention:
            named = [customer for customer in matches if customer.canonical_name.lower() == mention.strip().lower()]
            if len(named) == 1:
                return "ok", named[0]
        return "ambiguous", [customer.canonical_name for customer in matches]
    if mention and (existing := _customer_by_name(db, trader_id, mention)):
        return "ok", existing
    candidate, confidence = match_customer(text, _customer_list(db, trader_id))
    if candidate and confidence >= 0.85:
        customer = _customer_by_name(db, trader_id, candidate)
        _add_alias(db, customer, mention)
        return "ok", customer
    if candidate and confidence >= 0.5:
        return "confirm", candidate
    if mention:
        return "new", mention
    return "none", None


def _customer_name(db: Session, customer_id: int | None) -> str | None:
    if customer_id is None:
        return None
    customer = db.get(Customer, customer_id)
    return customer.canonical_name if customer else None


def _entry_response(db: Session, entry: Entry) -> EntryResponse:
    return EntryResponse(
        id=entry.id, type=entry.type, item=entry.item, quantity=entry.quantity, unit=entry.unit,
        amount_ngn=entry.amount_ngn, customer=_customer_name(db, entry.customer_id),
        due_date=entry.due_date.date() if entry.due_date else None,
        confidence=entry.confidence, status=entry.status, stock_warning=entry.stock_warning,
        raw_text=entry.raw_text, created_at=entry.created_at,
    )


def _confirmation(entry: Entry, customer_name: str | None, verb: str = "Recorded") -> str:
    unit = f"{entry.unit}s" if entry.unit and entry.quantity is not None and entry.quantity > 1 and not entry.unit.endswith("s") and entry.unit != "kg" else entry.unit
    what = " ".join(part for part in (f"{entry.quantity:g} {unit}" if entry.quantity is not None and entry.unit else "", entry.item or "") if part)
    parts = [entry.type.replace("_", " "), what, f"₦{entry.amount_ngn:,}", customer_name or "", f"due {entry.due_date:%a %d %b}" if entry.due_date else ""]
    return f"{verb}: {', '.join(part for part in parts if part)}."


def _sync_stock(db: Session, trader_id: int, entry: Entry) -> None:
    """FR-S25/S26: keep at most one stock movement per entry, updated in place on corrections."""
    movement = db.scalar(select(StockMovement).where(StockMovement.entry_id == entry.id))
    item = None
    if entry.item:
        item = db.scalar(select(InventoryItem).where(InventoryItem.trader_id == trader_id, func.lower(InventoryItem.name) == entry.item.lower()))
    entry.inventory_item_id = item.id if item else None
    entry.stock_warning = None
    if entry.unit is None and item is not None and entry.quantity is not None:
        entry.unit = item.unit
    same_unit = item is not None and entry.quantity is not None and normalize_unit(entry.unit) == normalize_unit(item.unit)

    change = None
    reason = None
    if same_unit and entry.type in {"sale", "credit_sale"}:
        on_hand = db.scalar(select(func.coalesce(func.sum(StockMovement.quantity_change), 0)).where(StockMovement.inventory_item_id == item.id)) or 0
        available = on_hand - (movement.quantity_change if movement and movement.inventory_item_id == item.id else 0)
        if available >= entry.quantity:
            change, reason = -entry.quantity, "sale"
        else:
            entry.stock_warning = "check_stock"
    elif same_unit and entry.type == "expense":
        change, reason = entry.quantity, "restock"
    elif entry.type in {"sale", "credit_sale"} and entry.item and item is None:
        entry.stock_warning = "not_in_inventory"

    if change is None:
        if movement:
            db.delete(movement)
    elif movement:
        movement.inventory_item_id, movement.quantity_change, movement.reason = item.id, change, reason
    else:
        db.add(StockMovement(inventory_item_id=item.id, entry_id=entry.id, quantity_change=change, reason=reason))


def _save_entry(db: Session, trader: Trader, data: EntryData, raw_text: str, customer: Customer | None) -> Entry:
    due_at = datetime.combine(data.due_date, datetime.min.time(), UTC) if data.due_date else None
    entry = Entry(
        trader_id=trader.id, customer_id=customer.id if customer else None, type=data.type,
        item=data.item, quantity=data.quantity, unit=normalize_unit(data.unit), amount_ngn=data.amount_ngn,
        due_date=due_at, confidence=data.confidence, raw_text=raw_text, status="saved",
    )
    db.add(entry)
    db.flush()
    _sync_stock(db, trader.id, entry)
    return entry


def _entry_snapshot(db: Session, entry: Entry) -> dict[str, Any]:
    return {
        "item": entry.item, "quantity": entry.quantity, "unit": entry.unit, "amount_ngn": entry.amount_ngn,
        "customer": _customer_name(db, entry.customer_id), "due_date": entry.due_date.date().isoformat() if entry.due_date else None,
    }


def _apply_correction(db: Session, trader: Trader, entry: Entry, text: str) -> MessageResponse:
    """FR-S6: update the last entry in place and record the edit."""
    old_values = _entry_snapshot(db, entry)
    changes = extract_correction(text, {**old_values, "type": entry.type})
    if not changes:
        return MessageResponse(status="clarify", question="What should I change on the last entry?")
    if "customer" in changes:
        status, value = _resolve_customer(db, trader.id, text, changes["customer"])
        customer = value if status == "ok" else _create_customer(db, trader.id, changes["customer"]) if status == "new" else None
        if customer is None:
            return MessageResponse(status="clarify", question="Which customer do you mean?")
        entry.customer_id = customer.id
    for field in ("item", "quantity", "amount_ngn"):
        if field in changes:
            setattr(entry, field, changes[field])
    if "unit" in changes:
        entry.unit = normalize_unit(changes["unit"])
    if "due_date" in changes:
        try:
            entry.due_date = datetime.combine(date.fromisoformat(str(changes["due_date"])), datetime.min.time(), UTC)
        except ValueError:
            pass
    entry.updated_at = datetime.now(UTC)
    db.flush()
    _sync_stock(db, trader.id, entry)
    db.add(EntryEdit(entry_id=entry.id, old_values=old_values, new_values=_entry_snapshot(db, entry)))
    db.flush()
    customer_name = _customer_name(db, entry.customer_id)
    return MessageResponse(status="saved", updated=True, confirmation=_confirmation(entry, customer_name, "Updated"), entry=_entry_response(db, entry))


def _hold(db: Session, trader: Trader, pending: PendingClarification | None, payload: MessageRequest, partial: dict[str, Any], question: str) -> MessageResponse:
    if pending:
        pending.partial_entry = partial
        pending.question = question
    else:
        db.add(PendingClarification(trader_id=trader.id, client_message_id=payload.client_message_id, partial_entry=partial, question=question))
    return MessageResponse(status="clarify", question=question)


def _missing_question(data: EntryData) -> str | None:
    if data.amount_ngn is None:
        if data.quantity is not None and data.unit:
            return f"How much did you collect for the {data.quantity:g} {data.unit}{'s' if data.quantity > 1 and not data.unit.endswith('s') else ''}?"
        return "How much was it?"
    if data.type in {"credit_sale", "payment_received"} and not data.customer:
        return "Which customer is this for?"
    if data.confidence < 0.6:
        return "I didn't fully understand. What did you sell or spend, and for how much?"
    return None


def _base_context(db: Session, trader: Trader, last_entry: Entry | None) -> dict[str, Any]:
    context: dict[str, Any] = {
        "today": datetime.now(UTC).date().isoformat(),
        "trader_items": [name for (name,) in db.execute(select(InventoryItem.name).where(InventoryItem.trader_id == trader.id)).all()],
        "customers": _customer_list(db, trader.id),
    }
    if last_entry:
        context["last_entry"] = _entry_snapshot(db, last_entry)
    return context


def _is_fresh_entry(text: str, context: dict[str, Any]) -> bool:
    """While a question is waiting, a message that is a complete entry on its own starts over instead of answering it."""
    if len(text.split()) < 3:
        return False
    data = extract_entry(text, context)
    return data is not None and bool(data.item or data.customer) and _missing_question(data) is None


def _process_text(db: Session, trader: Trader, payload: MessageRequest, text: str) -> MessageResponse:
    pending = db.scalar(select(PendingClarification).where(PendingClarification.trader_id == trader.id).order_by(PendingClarification.id.desc()))
    last_entry = db.scalar(select(Entry).where(Entry.trader_id == trader.id).order_by(Entry.created_at.desc(), Entry.id.desc()))
    context = _base_context(db, trader, last_entry)

    if pending and not YES_PATTERN.search(text.casefold()) and _is_fresh_entry(text, context):
        db.delete(pending)
        db.flush()
        pending = None

    if pending is None and last_entry is not None and is_correction(text):
        return _apply_correction(db, trader, last_entry, text)

    # A "Do you mean Mama Ngozi?" question is waiting for a yes or no.
    if pending and pending.partial_entry.get("_confirm_customer"):
        partial = dict(pending.partial_entry)
        candidate, mention = partial.pop("_confirm_customer"), partial.pop("_mention", None)
        raw_text = partial.pop("raw_text", text)
        lowered = text.casefold()
        if YES_PATTERN.search(lowered):
            customer = _customer_by_name(db, trader.id, candidate)
            _add_alias(db, customer, mention)
        elif NO_PATTERN.search(lowered):
            named = [match for match in _alias_matches(db, trader.id, text) if match.canonical_name != candidate]
            if len(named) == 1:
                customer = named[0]
            elif mention:
                customer = _create_customer(db, trader.id, mention)
            else:
                return _hold(db, trader, pending, payload, {**partial, "raw_text": raw_text, "customer": None}, "Which customer is this for?")
        else:
            return MessageResponse(status="clarify", question=pending.question)
        data = EntryData.model_validate({**partial, "customer": customer.canonical_name, "confidence": max(partial.get("confidence", 0), 0.8)})
        entry = _save_entry(db, trader, data, raw_text, customer)
        db.delete(pending)
        return MessageResponse(status="saved", confirmation=_confirmation(entry, customer.canonical_name), entry=_entry_response(db, entry))

    if pending:
        context["pending_entry"] = {key: value for key, value in pending.partial_entry.items() if not key.startswith("_")}
        context["pending_question"] = pending.question

    extracted = extract_entry(text, context)
    if extracted is None:
        if pending:
            return MessageResponse(status="clarify", question=pending.question)
        return MessageResponse(status="fallback", question="I couldn't understand that clearly. Please say what happened and how much.")

    if pending and extracted.amount_ngn is not None:
        # The trader answered our own question; the answer completes the held entry.
        extracted = extracted.model_copy(update={"confidence": max(extracted.confidence, 0.6)})
    source_text = pending.partial_entry.get("raw_text", text) if pending else text
    partial = {**extracted.model_dump(mode="json"), "raw_text": source_text}

    customer = None
    if extracted.customer or extracted.type in {"credit_sale", "payment_received"}:
        status, value = _resolve_customer(db, trader.id, source_text if not pending else f"{source_text} {text}", extracted.customer)
        if status == "ok":
            customer = value
            extracted = extracted.model_copy(update={"customer": customer.canonical_name, "confidence": max(extracted.confidence, 0.6)})
            partial.update({"customer": customer.canonical_name, "confidence": extracted.confidence})
        elif status == "ambiguous":
            partial["customer"] = None
            return _hold(db, trader, pending, payload, partial, f"Do you mean {' or '.join(value)}?")
        elif status == "confirm" and extracted.amount_ngn is not None:
            partial.update({"_confirm_customer": value, "_mention": extracted.customer})
            return _hold(db, trader, pending, payload, partial, f"Do you mean {value}?")

    question = _missing_question(extracted)
    if question:
        return _hold(db, trader, pending, payload, partial, question)

    if customer is None and extracted.customer:
        customer = _create_customer(db, trader.id, extracted.customer)
    entry = _save_entry(db, trader, extracted, source_text, customer)
    if pending:
        db.delete(pending)
    return MessageResponse(status="saved", confirmation=_confirmation(entry, customer.canonical_name if customer else None), entry=_entry_response(db, entry))


@router.post("/messages", response_model=MessageResponse)
def process_message(payload: MessageRequest, trader: Trader = Depends(get_current_trader), db: Session = Depends(get_db)) -> MessageResponse:
    processed = db.scalar(select(ProcessedMessage).where(ProcessedMessage.trader_id == trader.id, ProcessedMessage.client_message_id == payload.client_message_id))
    if processed:
        return MessageResponse.model_validate(processed.response_payload)

    started = time.monotonic()
    transcript = None
    if payload.audio_base64:
        try:
            audio = base64.b64decode(payload.audio_base64, validate=True)
        except (binascii.Error, ValueError):
            raise HTTPException(status_code=422, detail={"error": {"code": "invalid_audio", "message": "audio_base64 is not valid base64."}})
        transcript = transcribe(audio, payload.audio_filename)
        if transcript is None:
            # Nothing is written, so the app can resend with the same client_message_id.
            return MessageResponse(status="fallback", question="I couldn't hear that clearly. Please resend the voice note or type it.")

    # raw_text keeps the trader's own words; extraction normalizes shorthand internally.
    text = " ".join((transcript or payload.text or "").split())
    response = _process_text(db, trader, payload, text)
    response.transcript = transcript
    if response.status != "fallback":
        db.add(ProcessedMessage(trader_id=trader.id, client_message_id=payload.client_message_id, response_payload=response.model_dump(mode="json")))
    db.commit()
    logger.info(
        "message trader=%s status=%s input=%r entry=%s confidence=%s latency_ms=%d",
        trader.id, response.status, text, response.entry.id if response.entry else None,
        response.entry.confidence if response.entry else None, (time.monotonic() - started) * 1000,
    )
    return response


@router.get("/entries", response_model=EntriesResponse)
def list_entries(
    period_start: date | None = None,
    period_end: date | None = None,
    entry_type: str | None = Query(default=None, alias="type"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    trader: Trader = Depends(get_current_trader),
    db: Session = Depends(get_db),
) -> EntriesResponse:
    query = select(Entry).where(Entry.trader_id == trader.id)
    if entry_type:
        query = query.where(Entry.type == entry_type)
    if period_start:
        query = query.where(Entry.created_at >= datetime.combine(period_start, datetime.min.time(), UTC))
    if period_end:
        query = query.where(Entry.created_at < datetime.combine(period_end.fromordinal(period_end.toordinal() + 1), datetime.min.time(), UTC))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.scalars(query.order_by(Entry.created_at.desc(), Entry.id.desc()).limit(limit).offset(offset)).all()
    return EntriesResponse(items=[_entry_response(db, entry) for entry in items], limit=limit, offset=offset, total=total)
