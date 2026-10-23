from pydantic import BaseModel

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
