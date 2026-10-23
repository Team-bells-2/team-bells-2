from __future__ import annotations

import re
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.customers.index import customer_balances
from app.inventory.models import InventoryItem, StockMovement
from app.ledger.models import Entry
from app.onboarding.models import Trader
from app.shared.Infrastructure.db.session import get_db
from app.shared.Infrastructure.llm.index import route_intent
from app.shared.auth import get_current_trader
from app.suggestions.index import rank_suppliers

router = APIRouter(prefix="/ask", tags=["ask"])

FALLBACK = "I can tell you who owes you, one customer's balance, today's sales, your stock, or where to restock."


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)


def _keyword_intent(question: str, customers: list[str], items: list[str]) -> dict | None:
    """Cheap routing for common phrasings; the model handles the rest (FR-S11)."""
    customer = next((name for name in customers if name.casefold() in question or name.casefold().split()[-1] in question.split()), None)
    item = next((name for name in items if name.casefold() in question), None)
    if re.search(r"where (i|i fit|can i|to|should i)\s*(fit\s+)?(buy|get|restock)|restock|who (dey|de|is) sell", question):
        return {"intent": "restock_suggestion", "item": item or next((word for word in ("rice", "beans", "garri", "oil") if word in question), None)}
    if re.search(r"\b(how much|wetin)\b.*\b(owe|dey owe)\b", question) and customer:
        return {"intent": "customer_balance", "customer": customer}
    if re.search(r"who (owes|dey owe|de owe|still owe)|who never pay|my debtors", question):
        return {"intent": "who_owes"}
    if re.search(r"(sell|sold|sales|make)\b.*\btoday\b|today('s)? sales", question):
        return {"intent": "today_total"}
    if re.search(r"\b(stock|remain|left|how many)\b", question) and item:
        return {"intent": "stock_level", "item": item}
    return None


@router.post("")
def ask(payload: AskRequest, trader: Trader = Depends(get_current_trader), db: Session = Depends(get_db)) -> dict:
    question = " ".join(payload.question.casefold().strip().rstrip("?!.").split())
    balances = customer_balances(db, trader.id)
    customer_names = [customer.canonical_name for customer, _, _ in balances]
    item_rows = db.scalars(select(InventoryItem).where(InventoryItem.trader_id == trader.id)).all()
    item_names = [item.name for item in item_rows]

    routed = _keyword_intent(question, customer_names, item_names) or route_intent(payload.question, customer_names, item_names) or {"intent": "unknown"}
    intent = routed["intent"]

    if intent == "who_owes":
        owing = [{"name": customer.canonical_name, "amount_owed_ngn": balance, "overdue": overdue} for customer, balance, overdue in balances if balance > 0]
        if not owing:
            return {"intent": intent, "answer": "Nobody owes you right now.", "customers": []}
        owing.sort(key=lambda row: -row["amount_owed_ngn"])
        answer = "; ".join(f"{row['name']} ₦{row['amount_owed_ngn']:,}{' (overdue)' if row['overdue'] else ''}" for row in owing)
        return {"intent": intent, "answer": f"{answer}. Total ₦{sum(row['amount_owed_ngn'] for row in owing):,}.", "customers": owing}

    if intent == "customer_balance" and routed.get("customer"):
        balance = next((balance for customer, balance, _ in balances if customer.canonical_name == routed["customer"]), 0)
        answer = f"{routed['customer']} owes you ₦{balance:,}." if balance > 0 else f"{routed['customer']} doesn't owe you anything."
        return {"intent": intent, "answer": answer, "customer": routed["customer"], "amount_owed_ngn": max(balance, 0)}

    if intent == "today_total":
        start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        sales = db.scalar(select(func.coalesce(func.sum(Entry.amount_ngn), 0)).where(
            Entry.trader_id == trader.id, Entry.type.in_(["sale", "credit_sale"]), Entry.created_at >= start,
        )) or 0
        return {"intent": intent, "answer": f"Today's recorded sales are ₦{int(sales):,}.", "sales_ngn": int(sales)}

    if intent == "stock_level" and routed.get("item"):
        item = next(row for row in item_rows if row.name == routed["item"])
        on_hand = db.scalar(select(func.coalesce(func.sum(StockMovement.quantity_change), 0)).where(StockMovement.inventory_item_id == item.id)) or 0
        return {"intent": intent, "answer": f"You have {float(on_hand):g} {item.unit} of {item.name} left.", "item": item.name, "quantity_on_hand": float(on_hand), "unit": item.unit}

    if intent == "restock_suggestion" and routed.get("item"):
        result = rank_suppliers(db, trader, routed["item"])
        if not result["suppliers"]:
            return {"intent": intent, "answer": f"I don't have supplier data for {routed['item']} yet.", **result}
        lines = [f"{index}. {row['supplier']} ({row['area']}), ₦{row['unit_price_ngn']:,} per {row['unit']}: {row['reason']}" for index, row in enumerate(result["suppliers"], start=1)]
        return {"intent": intent, "answer": "Demo data. " + " ".join(lines), **result}

    return {"intent": "unknown", "answer": FALLBACK}
