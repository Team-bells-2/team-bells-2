from fastapi import APIRouter, Depends

from app.inventory.dependencies import get_inventory_repository
from app.inventory.orchestrator import InventoryOrchestrator
from app.inventory.repositories.inventory_repository import InventoryRepository
from app.inventory.schemas import InventoryItemOut
from app.onboarding.models import Trader
from app.onboarding.router import get_current_trader

router = APIRouter(tags=["inventory"])


def get_inventory_orchestrator(
    inventory_repository: InventoryRepository = Depends(get_inventory_repository),
) -> InventoryOrchestrator:
    return InventoryOrchestrator(inventory_repository)


@router.get("/inventory", response_model=list[InventoryItemOut])
def list_inventory(
    trader: Trader = Depends(get_current_trader),
    orchestrator: InventoryOrchestrator = Depends(get_inventory_orchestrator),
) -> list[InventoryItemOut]:
    return orchestrator.list_items(trader.id)
