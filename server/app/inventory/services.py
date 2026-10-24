from decimal import Decimal

from app.inventory.models import InventoryItem
from app.inventory.schemas import InventoryItemOut


def is_low_stock(quantity_on_hand: Decimal, reorder_level: Decimal) -> bool:
    """At or below the reorder level (FR-S27, S32)."""
    return quantity_on_hand <= reorder_level


def movement_error(reason: str, quantity_change: Decimal, quantity_on_hand: Decimal) -> tuple[str, str] | None:
    """(code, message) when a manual stock movement breaks the rules (BR-I3), else None."""
    if quantity_change == 0:
        return "invalid_movement", "Quantity change cannot be zero."
    if reason in {"opening", "restock"} and quantity_change < 0:
        return "invalid_movement", "Opening and restock quantities must be positive."
    if quantity_on_hand + quantity_change < 0:
        return "negative_stock", "This change would make stock negative."
    return None


def to_item_out(item: InventoryItem, quantity_on_hand: Decimal) -> InventoryItemOut:
    on_hand = Decimal(quantity_on_hand)
    return InventoryItemOut(
        id=item.id,
        name=item.name,
        unit=item.unit,
        quantity_on_hand=on_hand,
        unit_cost_ngn=item.unit_cost_ngn,
        reorder_level=item.reorder_level,
        reorder_quantity=item.reorder_quantity,
        low_stock=is_low_stock(on_hand, item.reorder_level),
    )
