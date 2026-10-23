from fastapi import APIRouter, Depends, Query

from app.home.orchestrator import HomeOrchestrator
from app.home.schemas import HomeSummary
from app.inventory.dependencies import get_inventory_repository
from app.inventory.repositories.inventory_repository import InventoryRepository
from app.ledger.dependencies import get_entry_repository
from app.ledger.repositories.entry_repository import EntryRepository
from app.onboarding.models import Trader
from app.onboarding.router import get_current_trader
from app.shared.periods import Period

router = APIRouter(tags=["home"])


def get_home_orchestrator(
    entry_repository: EntryRepository = Depends(get_entry_repository),
    inventory_repository: InventoryRepository = Depends(get_inventory_repository),
) -> HomeOrchestrator:
    return HomeOrchestrator(entry_repository, inventory_repository)


@router.get("/home", response_model=HomeSummary)
def get_home(
    period: Period = Query(default="today"),
    trader: Trader = Depends(get_current_trader),
    orchestrator: HomeOrchestrator = Depends(get_home_orchestrator),
) -> HomeSummary:
    return orchestrator.get_summary(trader.id, period)
