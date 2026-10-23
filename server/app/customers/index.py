from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.customers.models import Customer, CustomerAlias
from app.ledger.models import Entry
from app.onboarding.models import Trader
from app.shared.Infrastructure.db.session import get_db
from app.shared.auth import get_current_trader

router = APIRouter(prefix="/customers", tags=["customers"])


def _aware(moment: datetime) -> datetime:
    # SQLite returns naive datetimes; everything is stored in UTC.
    return moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment


def customer_balances(db: Session, trader_id: int) -> list[tuple[Customer, int, bool]]:
    """FR-S10: balances derived from entries (credit sales add, payments subtract). Returns (customer, balance, overdue)."""
    customers = db.scalars(select(Customer).where(Customer.trader_id == trader_id).order_by(Customer.canonical_name)).all()
    entries = db.scalars(select(Entry).where(Entry.trader_id == trader_id, Entry.customer_id.is_not(None))).all()
    now = datetime.now(UTC)
    result = []
    for customer in customers:
        own = [entry for entry in entries if entry.customer_id == customer.id]
        balance = sum(entry.amount_ngn if entry.type == "credit_sale" else -entry.amount_ngn if entry.type == "payment_received" else 0 for entry in own)
        overdue = balance > 0 and any(entry.type == "credit_sale" and entry.due_date and _aware(entry.due_date) < now for entry in own)
        result.append((customer, balance, overdue))
    return result


@router.get("")
def list_customers(trader: Trader = Depends(get_current_trader), db: Session = Depends(get_db)) -> list[dict]:
    aliases = db.execute(select(CustomerAlias.customer_id, CustomerAlias.alias).join(Customer).where(Customer.trader_id == trader.id)).all()
    return [
        {
            "id": customer.id, "name": customer.canonical_name,
            "aliases": [alias for customer_id, alias in aliases if customer_id == customer.id and alias != customer.canonical_name],
            "amount_owed_ngn": max(balance, 0), "overdue": overdue,
        }
        for customer, balance, overdue in customer_balances(db, trader.id)
    ]
