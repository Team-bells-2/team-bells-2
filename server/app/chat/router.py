from fastapi import APIRouter, Depends, Query

from app.chat.dependencies import get_chat_repository
from app.chat.orchestrator import ChatOrchestrator
from app.chat.repositories.chat_repository import ChatRepository
from app.chat.schemas import ChatHistory
from app.onboarding.models import Trader
from app.onboarding.router import get_current_trader

router = APIRouter(tags=["chat"])


def get_chat_orchestrator(chat_repository: ChatRepository = Depends(get_chat_repository)) -> ChatOrchestrator:
    return ChatOrchestrator(chat_repository)


@router.get("/messages/history", response_model=ChatHistory)
def get_history(
    limit: int = Query(default=100, ge=1, le=500),
    before_id: int | None = Query(default=None, ge=1),
    trader: Trader = Depends(get_current_trader),
    orchestrator: ChatOrchestrator = Depends(get_chat_orchestrator),
) -> ChatHistory:
    """The trader's assistant chat, oldest first: the newest `limit` messages, or those before `before_id`."""
    return orchestrator.history(trader.id, limit, before_id)
