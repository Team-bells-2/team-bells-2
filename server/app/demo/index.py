from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.consent.models import AccessLog, AccessRequest, AccessToken
from app.customers.models import Customer, CustomerAlias
from app.inventory.models import InventoryItem, StockMovement
from app.ledger.models import Entry, EntryEdit, PendingClarification, ProcessedMessage
from app.onboarding.models import SessionToken, Trader
from app.shared.Infrastructure.db.session import get_db
from app.shared.auth import hash_pin, issue_session_token
from app.shared.env import settings
from app.suggestions.seed import seed_suppliers

router = APIRouter(tags=["demo"])
DASHBOARD_HTML = Path(__file__).with_name("dashboard.html")

DEMO_TRADER = {
    "name": "Tolu Adeyemi", "phone": "08030000001", "business_name": "Tolu Foodstuff Store",
    "sector": "foodstuff", "location_name": "Mushin Market", "latitude": 6.5336, "longitude": 3.3502,
}
DEMO_PIN = "1234"
# name, unit, unit cost, opening quantity, reorder level, reorder quantity
DEMO_ITEMS = [
    ("rice", "bag", 58000, 10, 3, 10),
    ("beans", "bag", 68000, 6, 2, 5),
    ("garri", "bag", 25000, 2, 3, 8),
    ("oil", "keg", 36000, 5, 2, 4),
]
DEMO_CUSTOMERS = {
    "Mama Ngozi": ["Ngozi", "the rice woman"],
    "Mr Bayo": ["Bayo", "Oga Bayo"],
    "Aunty Funke": ["Funke"],
    "Iya Sade": ["Sade", "the pepper seller"],
}

# Children before parents, so the reset works without database-level cascades.
TABLES_IN_DELETE_ORDER = [
    AccessLog, AccessToken, AccessRequest, StockMovement, EntryEdit, Entry, PendingClarification,
    ProcessedMessage, CustomerAlias, Customer, InventoryItem, SessionToken, Trader,
]


def _require_demo_controls() -> None:
    if not settings.DEMO_CONTROLS_ENABLED:
        raise HTTPException(status_code=403, detail={"error": {"code": "demo_controls_disabled", "message": "Set DEMO_CONTROLS_ENABLED=true to use demo controls."}})


@router.post("/demo/reset", dependencies=[Depends(_require_demo_controls)])
def reset_demo(db: Session = Depends(get_db)) -> dict:
    """FR-C10: no trader accounts, supplier and review data loaded."""
    for table in TABLES_IN_DELETE_ORDER:
        db.execute(delete(table))
    seed_suppliers(db)
    db.commit()
    return {"status": "reset"}


@router.post("/demo/seed", dependencies=[Depends(_require_demo_controls)])
def seed_demo(db: Session = Depends(get_db)) -> dict:
    """FR-C10: the demo trader, customers with nicknames, and starting stock. Safe to run twice."""
    seed_suppliers(db)
    trader = db.scalar(select(Trader).where(Trader.phone == DEMO_TRADER["phone"]))
    if trader is None:
        trader = Trader(**DEMO_TRADER, pin_hash=hash_pin(DEMO_PIN))
        db.add(trader)
        db.flush()
        for name, unit, cost, opening, reorder_level, reorder_quantity in DEMO_ITEMS:
            item = InventoryItem(trader_id=trader.id, name=name, unit=unit, unit_cost_ngn=cost, reorder_level=reorder_level, reorder_quantity=reorder_quantity)
            db.add(item)
            db.flush()
            db.add(StockMovement(inventory_item_id=item.id, quantity_change=opening, reason="opening"))
        for name, aliases in DEMO_CUSTOMERS.items():
            customer = Customer(trader_id=trader.id, canonical_name=name)
            db.add(customer)
            db.flush()
            for alias in [name, *aliases]:
                db.add(CustomerAlias(customer_id=customer.id, alias=alias))
    token = issue_session_token(db, trader)
    db.commit()
    return {"status": "seeded", "trader_id": trader.id, "phone": trader.phone, "pin": DEMO_PIN, "session_token": token, "token_type": "bearer"}


@router.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
def dashboard() -> HTMLResponse:
    return HTMLResponse(DASHBOARD_HTML.read_text(encoding="utf-8"))
