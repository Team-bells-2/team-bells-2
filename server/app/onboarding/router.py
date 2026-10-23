from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.onboarding.dependencies import get_location_repository, get_session_repository, get_trader_repository
from app.onboarding.models import Trader
from app.onboarding.orchestrator import OnboardingOrchestrator
from app.onboarding.repositories.location_repository import LocationRepository
from app.onboarding.repositories.session_repository import SessionRepository
from app.onboarding.repositories.trader_repository import TraderRepository
from app.onboarding.schemas import OnboardingRequest, OnboardingResponse, TraderOut

router = APIRouter(tags=["onboarding"])

_bearer = HTTPBearer(auto_error=False)


def get_onboarding_orchestrator(
    location_repository: LocationRepository = Depends(get_location_repository),
    trader_repository: TraderRepository = Depends(get_trader_repository),
    session_repository: SessionRepository = Depends(get_session_repository),
) -> OnboardingOrchestrator:
    return OnboardingOrchestrator(location_repository, trader_repository, session_repository)


def get_current_trader(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    orchestrator: OnboardingOrchestrator = Depends(get_onboarding_orchestrator),
) -> Trader:
    """Dependency for every trader endpoint: resolves the session token to its trader."""
    return orchestrator.authenticate_trader(credentials.credentials if credentials else None)


@router.post("/onboarding", response_model=OnboardingResponse, status_code=201)
def onboard(
    request: OnboardingRequest,
    orchestrator: OnboardingOrchestrator = Depends(get_onboarding_orchestrator),
) -> OnboardingResponse:
    token, trader = orchestrator.onboard_trader(request)
    return OnboardingResponse(token=token, trader=TraderOut.model_validate(trader))
