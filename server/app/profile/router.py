from fastapi import APIRouter, Depends

from app.onboarding.models import Trader
from app.onboarding.repositories.location_repository import LocationRepository
from app.onboarding.repositories.trader_repository import TraderRepository
from app.onboarding.dependencies import get_location_repository, get_trader_repository
from app.onboarding.router import get_current_trader
from app.profile.orchestrator import ProfileOrchestrator
from app.profile.schemas import ProfileOut, ProfileUpdate
from app.shared.Infrastructure.realtime.hub import EventPublisher, get_event_publisher

router = APIRouter(tags=["profile"])


def get_profile_orchestrator(
    location_repository: LocationRepository = Depends(get_location_repository),
    trader_repository: TraderRepository = Depends(get_trader_repository),
    events: EventPublisher = Depends(get_event_publisher),
) -> ProfileOrchestrator:
    return ProfileOrchestrator(location_repository, trader_repository, events)


@router.get("/profile", response_model=ProfileOut)
def get_profile(trader: Trader = Depends(get_current_trader)) -> Trader:
    return trader


@router.patch("/profile", response_model=ProfileOut)
def patch_profile(
    update: ProfileUpdate,
    trader: Trader = Depends(get_current_trader),
    orchestrator: ProfileOrchestrator = Depends(get_profile_orchestrator),
) -> Trader:
    return orchestrator.update_profile(trader, update)
