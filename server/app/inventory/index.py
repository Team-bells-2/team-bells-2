from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.inventory.models import InventoryItem, StockMovement
from app.inventory.schemas import InventoryCreate, InventoryItemResponse, InventoryUpdate, StockMovementCreate
from app.onboarding.models import Trader
from app.shared.Infrastructure.db.session import get_db
from app.shared.auth import get_current_trader

router = APIRouter(prefix="/inventory", tags=["inventory"])


def _to_response(db: Session, item: InventoryItem) -> InventoryItemResponse:
    quantity = db.scalar(select(func.coalesce(func.sum(StockMovement.quantity_change), 0)).where(StockMovement.inventory_item_id == item.id)) or 0
    return InventoryItemResponse(
        id=item.id, name=item.name, unit=item.unit, unit_cost_ngn=item.unit_cost_ngn,
        quantity_on_hand=float(quantity), reorder_level=item.reorder_level,
        reorder_quantity=item.reorder_quantity, low_stock=quantity <= item.reorder_level,
        created_at=item.created_at, updated_at=item.updated_at,
    )


@router.get("")
def list_inventory(trader: Trader = Depends(get_current_trader), db: Session = Depends(get_db)) -> list[InventoryItemResponse]:
    items = db.scalars(select(InventoryItem).where(InventoryItem.trader_id == trader.id).order_by(InventoryItem.name)).all()
    return [_to_response(db, item) for item in items]


@router.post("", status_code=201)
def create_inventory_item(payload: InventoryCreate, trader: Trader = Depends(get_current_trader), db: Session = Depends(get_db)) -> InventoryItemResponse:
    duplicate = db.scalar(select(InventoryItem).where(InventoryItem.trader_id == trader.id, func.lower(InventoryItem.name) == payload.name.strip().lower()))
    if duplicate:
        raise HTTPException(status_code=409, detail={"error": {"code": "item_exists", "message": "This inventory item already exists."}})
    item = InventoryItem(trader_id=trader.id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return _to_response(db, item)


@router.patch("/{item_id}")
def update_inventory_item(item_id: int, payload: InventoryUpdate, trader: Trader = Depends(get_current_trader), db: Session = Depends(get_db)) -> InventoryItemResponse:
    item = db.scalar(select(InventoryItem).where(InventoryItem.id == item_id, InventoryItem.trader_id == trader.id))
    if item is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "item_not_found", "message": "Inventory item not found."}})
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value.strip() if isinstance(value, str) else value)
    db.commit()
    db.refresh(item)
    return _to_response(db, item)


@router.post("/{item_id}/stock", status_code=201)
def add_stock_movement(item_id: int, payload: StockMovementCreate, trader: Trader = Depends(get_current_trader), db: Session = Depends(get_db)) -> InventoryItemResponse:
    item = db.scalar(select(InventoryItem).where(InventoryItem.id == item_id, InventoryItem.trader_id == trader.id))
    if item is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "item_not_found", "message": "Inventory item not found."}})
    if payload.reason not in {"adjustment", "sale"} and payload.quantity_change < 0:
        raise HTTPException(status_code=422, detail={"error": {"code": "invalid_movement", "message": "Opening and restock movements must be positive."}})
    if payload.reason == "sale" and payload.quantity_change > 0:
        raise HTTPException(status_code=422, detail={"error": {"code": "invalid_movement", "message": "Sale movement must reduce stock."}})
    current_quantity = db.scalar(select(func.coalesce(func.sum(StockMovement.quantity_change), 0)).where(StockMovement.inventory_item_id == item.id)) or 0
    if current_quantity + payload.quantity_change < 0:
        raise HTTPException(status_code=409, detail={"error": {"code": "negative_stock", "message": "This movement would make stock negative."}})
    db.add(StockMovement(inventory_item_id=item.id, **payload.model_dump()))
    db.commit()
    db.refresh(item)
    return _to_response(db, item)
