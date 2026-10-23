from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class InventoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    unit: str = Field(min_length=1, max_length=48)
    unit_cost_ngn: int = Field(default=0, ge=0)
    reorder_level: float = Field(default=0, ge=0)
    reorder_quantity: float = Field(default=0, ge=0)


class InventoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    unit: str | None = Field(default=None, min_length=1, max_length=48)
    unit_cost_ngn: int | None = Field(default=None, ge=0)
    reorder_level: float | None = Field(default=None, ge=0)
    reorder_quantity: float | None = Field(default=None, ge=0)


class StockMovementCreate(BaseModel):
    quantity_change: float
    reason: Literal["opening", "restock", "sale", "adjustment"]


class InventoryItemResponse(BaseModel):
    id: int
    name: str
    unit: str
    unit_cost_ngn: int
    quantity_on_hand: float
    reorder_level: float
    reorder_quantity: float
    low_stock: bool
    created_at: datetime
    updated_at: datetime
