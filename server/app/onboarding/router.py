from collections.abc import Callable
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Response, WebSocket, WebSocketDisconnect
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.inventory.dependencies import get_inventory_repository
from app.inventory.repositories.inventory_repository import InventoryRepository
from app.onboarding.dependencies import get_location_repository, get_session_repository, get_trader_repository
from app.onboarding.models import Trader, TraderSession
from app.onboarding.orchestrator import OnboardingOrchestrator
from app.onboarding.repositories.location_repository import LocationRepository
from app.onboarding.repositories.session_repository import SessionRepository
from app.onboarding.repositories.trader_repository import TraderRepository
from app.onboarding.schemas import ChangePinRequest, LoginRequest, OnboardingRequest, OnboardingResponse, TraderOut
from app.shared.env import settings
from app.shared.errors import AppError
from app.shared.Infrastructure.db.session import get_session_factory
from app.shared.Infrastructure.realtime.hub import SESSION_ENDED_CODE, EventPublisher, get_event_publisher, hub

router = APIRouter(tags=["onboarding"])

_bearer = HTTPBearer(auto_error=False)


def get_onboarding_orchestrator(
    location_repository: LocationRepository = Depends(get_location_repository),
    trader_repository: TraderRepository = Depends(get_trader_repository),
    session_repository: SessionRepository = Depends(get_session_repository),
    inventory_repository: InventoryRepository = Depends(get_inventory_repository),
    events: EventPublisher = Depends(get_event_publisher),
) -> OnboardingOrchestrator:
    return build_onboarding_orchestrator(
        location_repository, trader_repository, session_repository, inventory_repository, events
    )


def build_onboarding_orchestrator(
    location_repository: LocationRepository,
    trader_repository: TraderRepository,
    session_repository: SessionRepository,
    inventory_repository: InventoryRepository,
    events: EventPublisher,
) -> OnboardingOrchestrator:
    return OnboardingOrchestrator(
        location_repository,
        trader_repository,
        session_repository,
        inventory_repository,
        settings.SESSION_TOKEN_TTL_DAYS,
        settings.AUTH_MAX_FAILED_LOGINS,
        settings.AUTH_LOCK_MINUTES,
        events,
    )


def get_current_session(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    orchestrator: OnboardingOrchestrator = Depends(get_onboarding_orchestrator),
) -> TraderSession:
    return orchestrator.authenticate_session(credentials.credentials if credentials else None)


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


@router.post("/auth/login", response_model=OnboardingResponse)
def login(
    request: LoginRequest,
    orchestrator: OnboardingOrchestrator = Depends(get_onboarding_orchestrator),
) -> OnboardingResponse:
    token, trader = orchestrator.login(request.phone, request.pin)
    return OnboardingResponse(token=token, trader=TraderOut.model_validate(trader))


@router.post("/auth/logout", status_code=204)
def logout(
    session: TraderSession = Depends(get_current_session),
    orchestrator: OnboardingOrchestrator = Depends(get_onboarding_orchestrator),
) -> Response:
    orchestrator.logout(session)
    return Response(status_code=204)


@router.post("/auth/change-pin", status_code=204)
def change_pin(
    request: ChangePinRequest,
    trader: Trader = Depends(get_current_trader),
    orchestrator: OnboardingOrchestrator = Depends(get_onboarding_orchestrator),
) -> Response:
    orchestrator.change_pin(trader, request.current_pin, request.new_pin)
    return Response(status_code=204)


def _authenticate_socket(
    session_factory: Callable[[], Session], events: EventPublisher, token: str | None
) -> tuple[int, int, datetime] | None:
    """(trader id, session id, expiry), or None. Uses a short session that is closed before the
    socket starts listening, so an open socket never holds a database connection."""
    with session_factory() as db:
        orchestrator = build_onboarding_orchestrator(
            LocationRepository(db), TraderRepository(db), SessionRepository(db), InventoryRepository(db), events
        )
        try:
            session = orchestrator.authenticate_session(token)
        except AppError:
            return None
        return session.trader_id, session.id, orchestrator.session_expires_at(session)


@router.websocket("/ws")
async def websocket_events(
    websocket: WebSocket,
    token: str | None = Query(default=None),
    session_factory: Callable[[], Session] = Depends(get_session_factory),
    events: EventPublisher = Depends(get_event_publisher),
) -> None:
    """Change notifications for the trader of the session token (see shared/Infrastructure/realtime)."""
    identity = await run_in_threadpool(_authenticate_socket, session_factory, events, token)
    if identity is None:
        await websocket.accept()
        await websocket.close(code=SESSION_ENDED_CODE)
        return

    trader_id, session_id, expires_at = identity
    await hub.connect(trader_id, session_id, expires_at, websocket)
    try:
        while True:
            message = await websocket.receive_text()
            if hub.is_expired(trader_id, websocket):
                await websocket.close(code=SESSION_ENDED_CODE)
                break
            if message == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        hub.disconnect(trader_id, websocket)
