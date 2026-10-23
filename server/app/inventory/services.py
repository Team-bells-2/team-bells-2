from decimal import Decimal

from app.inventory.models import InventoryItem
from app.inventory.schemas import InventoryItemOut


def is_low_stock(quantity_on_hand: Decimal, reorder_level: Decimal) -> bool:
    """At or below the reorder level (FR-S27, S32)."""
    return quantity_on_hand <= reorder_level


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
