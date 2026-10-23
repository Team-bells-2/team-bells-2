from __future__ import annotations

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
from app.shared.Infrastructure.llm.index import extract_entry, normalize_naira_shorthand
from app.shared.auth import get_current_trader

router = APIRouter(tags=["ledger"])


def _customer_for_message(db: Session, trader_id: int, text: str, customer_name: str | None) -> Customer | None:
    aliases = db.execute(
        select(CustomerAlias.alias, Customer).join(Customer, Customer.id == CustomerAlias.customer_id).where(Customer.trader_id == trader_id)
    ).all()
    matching = [(alias, customer) for alias, customer in aliases if alias.casefold() in text.casefold()]
    unique = {customer.id: customer for _, customer in matching}
    if len(unique) == 1:
        return next(iter(unique.values()))
    if len(unique) > 1:
        raise HTTPException(status_code=409, detail={"error": {"code": "ambiguous_customer", "message": "More than one customer matches. Please clarify which customer."}})
    if customer_name:
        canonical = " ".join(customer_name.split()).strip()
        existing = db.scalar(select(Customer).where(Customer.trader_id == trader_id, func.lower(Customer.canonical_name) == canonical.lower()))
        if existing:
            return existing
        customer = Customer(trader_id=trader_id, canonical_name=canonical)
        db.add(customer)
        db.flush()
        db.add(CustomerAlias(customer_id=customer.id, alias=canonical))
        return customer
    return None


def _entry_response(entry: Entry) -> EntryResponse:
    return EntryResponse(
        id=entry.id, type=entry.type, item=entry.item, quantity=entry.quantity, unit=entry.unit,
        amount_ngn=entry.amount_ngn, customer=None, due_date=entry.due_date.date() if entry.due_date else None,
        confidence=entry.confidence, status=entry.status, stock_warning=entry.stock_warning,
        raw_text=entry.raw_text, created_at=entry.created_at,
    )


def _confirmation(entry: Entry, customer_name: str | None) -> str:
    label = entry.type.replace("_", " ")
    quantity = f", {entry.quantity:g} {entry.unit}" if entry.quantity is not None and entry.unit else ""
    item = f" {entry.item}" if entry.item else ""
    customer = f", {customer_name}" if customer_name else ""
    return f"Recorded: {label},{quantity}{item}, ₦{entry.amount_ngn:,}{customer}."


def _save_entry(db: Session, trader: Trader, data: EntryData, raw_text: str, client_message_id: str) -> Entry:
    if data.amount_ngn is None:
        raise ValueError("amount_ngn is required")
    if data.type in {"credit_sale", "payment_received"} and not data.customer:
        raise ValueError("customer is required")
    customer = _customer_for_message(db, trader.id, raw_text, data.customer)
    inventory_item = None
    if data.item:
        inventory_item = db.scalar(select(InventoryItem).where(InventoryItem.trader_id == trader.id, func.lower(InventoryItem.name) == data.item.lower()))
    stock_warning = None
    due_at = datetime.combine(data.due_date, datetime.min.time(), UTC) if data.due_date else None
    entry = Entry(
        trader_id=trader.id, customer_id=customer.id if customer else None,
        inventory_item_id=inventory_item.id if inventory_item else None, type=data.type,
        item=data.item, quantity=data.quantity, unit=data.unit, amount_ngn=data.amount_ngn,
        due_date=due_at, confidence=data.confidence, raw_text=raw_text, status="saved",
    )
    db.add(entry)
    db.flush()

    if inventory_item and data.quantity is not None and data.unit and inventory_item.unit.casefold() == data.unit.casefold():
        on_hand = db.scalar(select(func.coalesce(func.sum(StockMovement.quantity_change), 0)).where(StockMovement.inventory_item_id == inventory_item.id)) or 0
        if data.type in {"sale", "credit_sale"}:
            if on_hand >= data.quantity:
                db.add(StockMovement(inventory_item_id=inventory_item.id, entry_id=entry.id, quantity_change=-data.quantity, reason="sale"))
            else:
                stock_warning = "check_stock"
        elif data.type == "expense":
            db.add(StockMovement(inventory_item_id=inventory_item.id, entry_id=entry.id, quantity_change=data.quantity, reason="restock"))
    elif data.type in {"sale", "credit_sale"} and data.item:
        stock_warning = "not_in_inventory"
    entry.stock_warning = stock_warning
    return entry


@router.post("/messages", response_model=MessageResponse)
def process_message(payload: MessageRequest, trader: Trader = Depends(get_current_trader), db: Session = Depends(get_db)) -> MessageResponse:
    processed = db.scalar(select(ProcessedMessage).where(ProcessedMessage.trader_id == trader.id, ProcessedMessage.client_message_id == payload.client_message_id))
    if processed:
        return MessageResponse.model_validate(processed.response_payload)

    text = normalize_naira_shorthand(payload.text or "")
    pending = db.scalar(select(PendingClarification).where(PendingClarification.trader_id == trader.id).order_by(PendingClarification.id.desc()))
    last_entry = db.scalar(select(Entry).where(Entry.trader_id == trader.id).order_by(Entry.created_at.desc(), Entry.id.desc()))
    context: dict[str, Any] = {"trader_items": [name for (name,) in db.execute(select(InventoryItem.name).where(InventoryItem.trader_id == trader.id)).all()]}
    if pending:
        context["pending_entry"] = pending.partial_entry
        context["pending_message"] = pending.partial_entry.get("raw_text")
    if last_entry:
        context["last_entry"] = {key: getattr(last_entry, key) for key in ("type", "item", "quantity", "unit", "amount_ngn", "due_date")}
    try:
        extracted = extract_entry(text, context)
    except Exception:
        extracted = None
    if extracted is None:
        response = MessageResponse(status="fallback", question="I couldn't understand that clearly. Please say what happened and how much.")
    else:
        missing = []
        if extracted.amount_ngn is None:
            missing.append("amount_ngn")
        if extracted.type in {"credit_sale", "payment_received"} and not extracted.customer:
            missing.append("customer")
        if extracted.confidence < 0.6:
            missing.append("confidence")
        if missing:
            question = "How much was it?" if "amount_ngn" in missing else "Which customer do you mean?"
            partial = extracted.model_dump(mode="json")
            partial["raw_text"] = pending.partial_entry.get("raw_text", text) if pending else text
            if pending:
                pending.partial_entry = partial
                pending.question = question
            else:
                db.add(PendingClarification(trader_id=trader.id, client_message_id=payload.client_message_id, partial_entry=partial, question=question))
            response = MessageResponse(status="clarify", question=question)
        else:
            source_text = pending.partial_entry.get("raw_text", text) if pending else text
            entry = _save_entry(db, trader, extracted, source_text, payload.client_message_id)
            db.flush()
            customer_name = extracted.customer
            response = MessageResponse(status="saved", confirmation=_confirmation(entry, customer_name), entry=_entry_response(entry))
            if pending:
                db.delete(pending)
    db.add(ProcessedMessage(trader_id=trader.id, client_message_id=payload.client_message_id, response_payload=response.model_dump(mode="json")))
    db.commit()
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
    total = len(db.scalars(query).all())
    items = db.scalars(query.order_by(Entry.created_at.desc(), Entry.id.desc()).limit(limit).offset(offset)).all()
    return EntriesResponse(items=[_entry_response(entry) for entry in items], limit=limit, offset=offset, total=total)
