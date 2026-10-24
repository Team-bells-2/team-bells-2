from fastapi import APIRouter, Depends

from app.customers.dependencies import get_customer_repository
from app.customers.repositories.customer_repository import CustomerRepository
from app.demo.dependencies import get_seed_repository
from app.demo.orchestrator import DemoOrchestrator
from app.demo.repositories.seed_repository import SeedRepository
from app.demo.schemas import DemoSeedResult, ResetResult
from app.inventory.dependencies import get_inventory_repository
from app.inventory.repositories.inventory_repository import InventoryRepository
from app.onboarding.dependencies import get_location_repository, get_session_repository, get_trader_repository
from app.onboarding.repositories.location_repository import LocationRepository
from app.onboarding.repositories.session_repository import SessionRepository
from app.onboarding.repositories.trader_repository import TraderRepository
from app.shared.env import settings
from app.shared.errors import AppError

router = APIRouter(tags=["demo"])


def require_demo_controls() -> None:
    """Demo reset/seed only when DEMO_CONTROLS_ENABLED=true; never on a shared deployment (FR-C10)."""
    if not settings.DEMO_CONTROLS_ENABLED:
        raise AppError(403, "demo_controls_disabled", "Set DEMO_CONTROLS_ENABLED=true to use demo controls.")


def get_demo_orchestrator(
    seed_repository: SeedRepository = Depends(get_seed_repository),
    location_repository: LocationRepository = Depends(get_location_repository),
    trader_repository: TraderRepository = Depends(get_trader_repository),
    session_repository: SessionRepository = Depends(get_session_repository),
    inventory_repository: InventoryRepository = Depends(get_inventory_repository),
    customer_repository: CustomerRepository = Depends(get_customer_repository),
) -> DemoOrchestrator:
    return DemoOrchestrator(
        seed_repository,
        location_repository,
        trader_repository,
        session_repository,
        inventory_repository,
        customer_repository,
        settings.SESSION_TOKEN_TTL_DAYS,
    )


@router.post("/demo/reset", response_model=ResetResult, dependencies=[Depends(require_demo_controls)])
def reset_demo(orchestrator: DemoOrchestrator = Depends(get_demo_orchestrator)) -> ResetResult:
    return orchestrator.reset()


@router.post("/demo/seed", response_model=DemoSeedResult, dependencies=[Depends(require_demo_controls)])
def seed_demo(orchestrator: DemoOrchestrator = Depends(get_demo_orchestrator)) -> DemoSeedResult:
    return orchestrator.seed_demo()
