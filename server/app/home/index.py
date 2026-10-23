from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.customers.models import Customer
from app.inventory.models import InventoryItem, StockMovement
from app.ledger.models import Entry
from app.onboarding.models import Trader
from app.shared.Infrastructure.db.session import get_db
from app.shared.auth import get_current_trader

router = APIRouter(prefix="/home", tags=["home"])
Period = Literal["today", "7d", "30d"]


@router.get("")
def get_home(
    period: Period = Query(default="today"),
    trader: Trader = Depends(get_current_trader),
    db: Session = Depends(get_db),
) -> dict:
    now = datetime.now(UTC)
    if period == "today":
        start = datetime.combine(now.date(), time.min, UTC)
    elif period == "7d":
        start = now - timedelta(days=7)
    else:
        start = now - timedelta(days=30)

    rows = db.execute(
        select(Entry.type, func.coalesce(func.sum(Entry.amount_ngn), 0))
        .where(Entry.trader_id == trader.id, Entry.created_at >= start)
        .group_by(Entry.type)
    ).all()
    totals = {entry_type: int(amount) for entry_type, amount in rows}
    revenue = totals.get("sale", 0) + totals.get("credit_sale", 0)
    expenses = totals.get("expense", 0)

    customers = db.scalars(select(Customer).where(Customer.trader_id == trader.id)).all()
    total_owed = 0
    for customer in customers:
        customer_total = db.scalar(select(func.coalesce(func.sum(
            case((Entry.type == "credit_sale", Entry.amount_ngn), else_=0) -
            case((Entry.type == "payment_received", Entry.amount_ngn), else_=0)
        ), 0)).where(Entry.trader_id == trader.id, Entry.customer_id == customer.id)) or 0
        total_owed += max(int(customer_total), 0)

    items = db.scalars(select(InventoryItem).where(InventoryItem.trader_id == trader.id)).all()
    low_stock = []
    for item in items:
        on_hand = db.scalar(select(func.coalesce(func.sum(StockMovement.quantity_change), 0)).where(StockMovement.inventory_item_id == item.id)) or 0
        if on_hand <= item.reorder_level:
            low_stock.append({"item_id": item.id, "name": item.name, "quantity_on_hand": float(on_hand), "unit": item.unit, "reorder_level": item.reorder_level})

    item_count = db.scalar(select(func.count(Entry.id)).where(Entry.trader_id == trader.id, Entry.created_at >= start)) or 0
    return {
        "period": period,
        "revenue_ngn": revenue,
        "expenses_ngn": expenses,
        "profit_ngn": revenue - expenses,
        "total_owed_ngn": total_owed,
        "items_logged": int(item_count),
        "low_stock_items": low_stock,
    }
