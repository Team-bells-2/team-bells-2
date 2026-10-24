from app.inventory import services
from app.inventory.models import InventoryItem, StockMovement
from app.inventory.repositories.inventory_repository import InventoryRepository
from app.inventory.schemas import InventoryItemCreate, InventoryItemOut, InventoryItemUpdate, StockMovementCreate
from app.shared.errors import AppError


class InventoryOrchestrator:
    def __init__(self, inventory_repository: InventoryRepository):
        self.inventory_repository = inventory_repository

    def list_items(self, trader_id: int) -> list[InventoryItemOut]:
        return [
            services.to_item_out(item, quantity_on_hand)
            for item, quantity_on_hand in self.inventory_repository.list_items_with_quantity(trader_id)
        ]

    def create_item(self, trader_id: int, request: InventoryItemCreate) -> InventoryItemOut:
        """FR-S23: names are unique per trader, ignoring case (BR-I1)."""
        if self.inventory_repository.get_item_by_name(trader_id, request.name) is not None:
            raise AppError(409, "item_exists", f"'{request.name}' is already in your inventory.")
        try:
            item = self.inventory_repository.create_item(InventoryItem(trader_id=trader_id, **request.model_dump()))
            self.inventory_repository.commit()
        except Exception:
            self.inventory_repository.rollback()
            raise
        self.inventory_repository.refresh(item)
        return services.to_item_out(item, self.inventory_repository.get_quantity_on_hand(item.id))

    def update_item(self, trader_id: int, item_id: int, request: InventoryItemUpdate) -> InventoryItemOut:
        """Edits details only; quantity on hand is untouched (BR-I2)."""
        item = self._get_item(trader_id, item_id)
        changes = request.model_dump(exclude_unset=True)
        if "name" in changes:
            same_name = self.inventory_repository.get_item_by_name(trader_id, changes["name"])
            if same_name is not None and same_name.id != item.id:
                raise AppError(409, "item_exists", f"'{changes['name']}' is already in your inventory.")
        try:
            for field, value in changes.items():
                setattr(item, field, value)
            self.inventory_repository.commit()
        except Exception:
            self.inventory_repository.rollback()
            raise
        self.inventory_repository.refresh(item)
        return services.to_item_out(item, self.inventory_repository.get_quantity_on_hand(item.id))

    def add_stock(self, trader_id: int, item_id: int, request: StockMovementCreate) -> InventoryItemOut:
        """FR-S24: opening, restock or adjustment. Quantity on hand is the sum of movements."""
        item = self._get_item(trader_id, item_id)
        on_hand = self.inventory_repository.get_quantity_on_hand(item.id)
        error = services.movement_error(request.reason, request.quantity_change, on_hand)
        if error:
            status = 409 if error[0] == "negative_stock" else 422
            raise AppError(status, error[0], error[1])
        try:
            self.inventory_repository.add_movement(
                StockMovement(inventory_item_id=item.id, quantity_change=request.quantity_change, reason=request.reason)
            )
            self.inventory_repository.commit()
        except Exception:
            self.inventory_repository.rollback()
            raise
        return services.to_item_out(item, self.inventory_repository.get_quantity_on_hand(item.id))

    def _get_item(self, trader_id: int, item_id: int) -> InventoryItem:
        item = self.inventory_repository.get_item(trader_id, item_id)
        if item is None:
            raise AppError(404, "item_not_found", "Inventory item not found.")
        return item
