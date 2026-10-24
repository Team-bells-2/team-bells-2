from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy import Row, func, select

from app.inventory.models import InventoryItem, StockMovement
from app.shared.Infrastructure.db.base_repository import BaseRepository
from app.shared.matching import match_key


class InventoryRepository(BaseRepository):
    def get_item_by_name(self, trader_id: int, name: str) -> InventoryItem | None:
        """Matched with match_key (case, spaces and a plural ending ignored). A trader's inventory is
        small, so the comparison is done here rather than in SQL."""
        key = match_key(name)
        items = self.db.scalars(select(InventoryItem).where(InventoryItem.trader_id == trader_id)).all()
        return next((item for item in items if match_key(item.name) == key), None)

    def get_item(self, trader_id: int, item_id: int) -> InventoryItem | None:
        return self.db.scalar(
            select(InventoryItem).where(InventoryItem.trader_id == trader_id, InventoryItem.id == item_id)
        )

    def create_item(self, item: InventoryItem) -> InventoryItem:
        self.db.add(item)
        self.db.flush()
        return item

    def list_items_with_quantity(self, trader_id: int) -> Sequence[Row[tuple[InventoryItem, Decimal]]]:
        """Each item with its quantity on hand, derived from movements in one query."""
        on_hand = func.coalesce(func.sum(StockMovement.quantity_change), 0)
        return self.db.execute(
            select(InventoryItem, on_hand)
            .outerjoin(StockMovement, StockMovement.inventory_item_id == InventoryItem.id)
            .where(InventoryItem.trader_id == trader_id)
            .group_by(InventoryItem.id)
            .order_by(InventoryItem.name)
        ).all()

    def get_quantity_on_hand(self, inventory_item_id: int) -> Decimal:
        total = self.db.scalar(
            select(func.coalesce(func.sum(StockMovement.quantity_change), 0)).where(
                StockMovement.inventory_item_id == inventory_item_id
            )
        )
        return Decimal(total or 0)

    def get_movement_for_entry(self, entry_id: int) -> StockMovement | None:
        return self.db.scalar(select(StockMovement).where(StockMovement.entry_id == entry_id))

    def add_movement(self, movement: StockMovement) -> StockMovement:
        self.db.add(movement)
        self.db.flush()
        return movement

    def delete_movement(self, movement: StockMovement) -> None:
        self.db.delete(movement)
        self.db.flush()
