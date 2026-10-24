from fastapi import APIRouter, Depends, Header, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.consent.dependencies import get_access_repository
from app.consent.orchestrator import ConsentOrchestrator
from app.consent.repositories.access_repository import AccessRepository
from app.consent.schemas import (
    AccessDecision,
    AccessRequestCreate,
    AccessRequestCreated,
    AccessRequestOut,
    AccessRequestStatus,
    AgentSummary,
    RequestStatus,
)
from app.ledger.dependencies import get_entry_repository
from app.ledger.repositories.entry_repository import EntryRepository
from app.onboarding.dependencies import get_trader_repository
from app.onboarding.models import Trader
from app.onboarding.repositories.trader_repository import TraderRepository
from app.onboarding.router import get_current_trader
from app.shared.env import settings
from app.shared.Infrastructure.realtime.hub import EventPublisher, get_event_publisher

router = APIRouter(tags=["consent"])

# The agent's access token, separate from the trader's session token.
_agent_bearer = HTTPBearer(auto_error=False)


def get_consent_orchestrator(
    access_repository: AccessRepository = Depends(get_access_repository),
    trader_repository: TraderRepository = Depends(get_trader_repository),
    entry_repository: EntryRepository = Depends(get_entry_repository),
    events: EventPublisher = Depends(get_event_publisher),
) -> ConsentOrchestrator:
    return ConsentOrchestrator(
        access_repository, trader_repository, entry_repository, settings.ACCESS_TOKEN_TTL_MINUTES, events
    )


@router.post("/access-requests", response_model=AccessRequestCreated, status_code=202)
def create_access_request(
    request: AccessRequestCreate,
    orchestrator: ConsentOrchestrator = Depends(get_consent_orchestrator),
) -> AccessRequestCreated:
    """Lender agent, no auth: returns no business data."""
    return orchestrator.create_request(request)


@router.get("/access-requests/{request_id}/status", response_model=AccessRequestStatus, response_model_exclude_none=True)
def access_request_status(
    request_id: int,
    x_claim_secret: str = Header(min_length=8),
    orchestrator: ConsentOrchestrator = Depends(get_consent_orchestrator),
) -> AccessRequestStatus:
    """Lender agent polls with the claim secret; the token is returned once after approval."""
    return orchestrator.request_status(request_id, x_claim_secret)


@router.get("/agent/summary", response_model=AgentSummary, response_model_exclude_none=True)
def agent_summary(
    credentials: HTTPAuthorizationCredentials | None = Depends(_agent_bearer),
    orchestrator: ConsentOrchestrator = Depends(get_consent_orchestrator),
) -> AgentSummary:
    return orchestrator.agent_summary(credentials.credentials if credentials else None)


@router.get("/access-requests", response_model=list[AccessRequestOut])
def list_access_requests(
    status: RequestStatus | None = Query(default=None),
    trader: Trader = Depends(get_current_trader),
    orchestrator: ConsentOrchestrator = Depends(get_consent_orchestrator),
) -> list[AccessRequestOut]:
    return orchestrator.list_requests(trader.id, status)


@router.post("/access-requests/{request_id}/approve", response_model=AccessRequestOut)
def decide_access_request(
    request_id: int,
    decision: AccessDecision,
    trader: Trader = Depends(get_current_trader),
    orchestrator: ConsentOrchestrator = Depends(get_consent_orchestrator),
) -> AccessRequestOut:
    return orchestrator.decide(trader.id, request_id, decision.approve)


@router.delete("/access/{request_id}", response_model=AccessRequestOut)
def revoke_access(
    request_id: int,
    trader: Trader = Depends(get_current_trader),
    orchestrator: ConsentOrchestrator = Depends(get_consent_orchestrator),
) -> AccessRequestOut:
    return orchestrator.revoke(trader.id, request_id)
