from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.shared.types import Money, Quantity


class InventoryItemOut(BaseModel):
    id: int
    name: str
    unit: str
    quantity_on_hand: Quantity
    unit_cost_ngn: Money | None
    reorder_level: Quantity
    reorder_quantity: Quantity
    low_stock: bool


class InventoryItemCreate(BaseModel):
    """FR-S23. Reorder values start at 0, matching the table defaults."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    unit: str = Field(min_length=1, max_length=40)
    unit_cost_ngn: Decimal | None = Field(default=None, ge=0)
    reorder_level: Decimal = Field(default=Decimal(0), ge=0)
    reorder_quantity: Decimal = Field(default=Decimal(0), ge=0)


class InventoryItemUpdate(BaseModel):
    """Details only. Quantity on hand is never edited here; it changes through stock movements (FR-S23)."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=100)
    unit: str | None = Field(default=None, min_length=1, max_length=40)
    unit_cost_ngn: Decimal | None = Field(default=None, ge=0)
    reorder_level: Decimal | None = Field(default=None, ge=0)
    reorder_quantity: Decimal | None = Field(default=None, ge=0)


class StockMovementCreate(BaseModel):
    """FR-S24. Sales are recorded through the ledger, never here."""

    model_config = ConfigDict(extra="forbid")

    quantity_change: Decimal
    reason: Literal["opening", "restock", "adjustment"]
