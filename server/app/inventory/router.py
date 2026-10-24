from fastapi import APIRouter, Depends

from app.inventory.dependencies import get_inventory_repository
from app.inventory.orchestrator import InventoryOrchestrator
from app.inventory.repositories.inventory_repository import InventoryRepository
from app.inventory.schemas import InventoryItemCreate, InventoryItemOut, InventoryItemUpdate, StockMovementCreate
from app.onboarding.models import Trader
from app.onboarding.router import get_current_trader
from app.shared.Infrastructure.realtime.hub import EventPublisher, get_event_publisher

router = APIRouter(tags=["inventory"])


def get_inventory_orchestrator(
    inventory_repository: InventoryRepository = Depends(get_inventory_repository),
    events: EventPublisher = Depends(get_event_publisher),
) -> InventoryOrchestrator:
    return InventoryOrchestrator(inventory_repository, events)


@router.get("/inventory", response_model=list[InventoryItemOut])
def list_inventory(
    trader: Trader = Depends(get_current_trader),
    orchestrator: InventoryOrchestrator = Depends(get_inventory_orchestrator),
) -> list[InventoryItemOut]:
    return orchestrator.list_items(trader.id)


@router.post("/inventory", response_model=InventoryItemOut, status_code=201)
def create_inventory_item(
    request: InventoryItemCreate,
    trader: Trader = Depends(get_current_trader),
    orchestrator: InventoryOrchestrator = Depends(get_inventory_orchestrator),
) -> InventoryItemOut:
    return orchestrator.create_item(trader.id, request)


@router.patch("/inventory/{item_id}", response_model=InventoryItemOut)
def update_inventory_item(
    item_id: int,
    request: InventoryItemUpdate,
    trader: Trader = Depends(get_current_trader),
    orchestrator: InventoryOrchestrator = Depends(get_inventory_orchestrator),
) -> InventoryItemOut:
    return orchestrator.update_item(trader.id, item_id, request)


@router.post("/inventory/{item_id}/stock", response_model=InventoryItemOut, status_code=201)
def add_stock_movement(
    item_id: int,
    request: StockMovementCreate,
    trader: Trader = Depends(get_current_trader),
    orchestrator: InventoryOrchestrator = Depends(get_inventory_orchestrator),
) -> InventoryItemOut:
    return orchestrator.add_stock(trader.id, item_id, request)
