from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.customers.models import Customer
from app.ledger.models import Entry
from app.onboarding.models import Trader
from app.shared.Infrastructure.db.session import get_db
from app.shared.auth import get_current_trader

router = APIRouter(prefix="/ask", tags=["ask"])


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)


@router.post("")
def ask(payload: AskRequest, trader: Trader = Depends(get_current_trader), db: Session = Depends(get_db)) -> dict:
    question = " ".join(payload.question.casefold().strip().rstrip("?!.").split())
    if question in {"who owes me", "who owes me money", "who dey owe me"}:
        customers = db.scalars(select(Customer).where(Customer.trader_id == trader.id).order_by(Customer.canonical_name)).all()
        owing = []
        for customer in customers:
            entries = db.scalars(select(Entry).where(Entry.trader_id == trader.id, Entry.customer_id == customer.id)).all()
            balance = sum(entry.amount_ngn if entry.type == "credit_sale" else -entry.amount_ngn if entry.type == "payment_received" else 0 for entry in entries)
            if balance > 0:
                owing.append({"name": customer.canonical_name, "amount_owed_ngn": balance})
        if not owing:
            return {"intent": "who_owes", "answer": "Nobody owes you right now.", "customers": []}
        names = ", ".join(f"{item['name']} ₦{item['amount_owed_ngn']:,}" for item in owing)
        return {"intent": "who_owes", "answer": names, "customers": owing}

    if question in {"how much did i sell today", "how much i sell today", "wetin i sell today"}:
        start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        sales = db.scalar(select(func.coalesce(func.sum(Entry.amount_ngn), 0)).where(
            Entry.trader_id == trader.id,
            Entry.type.in_(["sale", "credit_sale"]),
            Entry.created_at >= start,
        )) or 0
        return {"intent": "today_total", "answer": f"Today's recorded sales are ₦{sales:,}.", "sales_ngn": int(sales)}

    return {"intent": "unknown", "answer": "I can answer who owes you or how much you sold today so far."}
