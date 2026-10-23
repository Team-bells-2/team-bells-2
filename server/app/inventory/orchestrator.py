from app.inventory import services
from app.inventory.repositories.inventory_repository import InventoryRepository
from app.inventory.schemas import InventoryItemOut


class InventoryOrchestrator:
    def __init__(self, inventory_repository: InventoryRepository):
        self.inventory_repository = inventory_repository

    def list_items(self, trader_id: int) -> list[InventoryItemOut]:
        return [
            services.to_item_out(item, quantity_on_hand)
            for item, quantity_on_hand in self.inventory_repository.list_items_with_quantity(trader_id)
        ]
