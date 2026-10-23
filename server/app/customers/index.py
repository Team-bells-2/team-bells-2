from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.customers.models import Customer, CustomerAlias
from app.ledger.models import Entry
from app.onboarding.models import Trader
from app.shared.Infrastructure.db.session import get_db
from app.shared.auth import get_current_trader

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("")
def list_customers(trader: Trader = Depends(get_current_trader), db: Session = Depends(get_db)) -> list[dict]:
    customers = db.scalars(select(Customer).where(Customer.trader_id == trader.id).order_by(Customer.canonical_name)).all()
    result = []
    now = datetime.now(UTC)
    for customer in customers:
        entries = db.scalars(select(Entry).where(Entry.trader_id == trader.id, Entry.customer_id == customer.id)).all()
        balance = sum(entry.amount_ngn if entry.type == "credit_sale" else -entry.amount_ngn if entry.type == "payment_received" else 0 for entry in entries)
        aliases = db.scalars(select(CustomerAlias.alias).where(CustomerAlias.customer_id == customer.id)).all()
        overdue = any(entry.type == "credit_sale" and entry.due_date and entry.due_date < now and balance > 0 for entry in entries)
        result.append({"id": customer.id, "name": customer.canonical_name, "aliases": aliases, "amount_owed_ngn": max(balance, 0), "overdue": overdue})
    return result
