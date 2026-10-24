from fastapi import APIRouter, Depends

from app.ai.dependencies import get_ai_orchestrator
from app.ai.orchestrator import AIOrchestrator
from app.ask.orchestrator import AskOrchestrator
from app.ask.schemas import AskRequest, AskResponse
from app.customers.orchestrator import CustomerOrchestrator
from app.customers.router import get_customer_orchestrator
from app.inventory.dependencies import get_inventory_repository
from app.inventory.repositories.inventory_repository import InventoryRepository
from app.ledger.dependencies import get_entry_repository
from app.ledger.repositories.entry_repository import EntryRepository
from app.onboarding.models import Trader
from app.onboarding.router import get_current_trader
from app.suggestions.orchestrator import SuggestionOrchestrator
from app.suggestions.router import get_suggestion_orchestrator

router = APIRouter(tags=["ask"])


def get_ask_orchestrator(
    customer_orchestrator: CustomerOrchestrator = Depends(get_customer_orchestrator),
    entry_repository: EntryRepository = Depends(get_entry_repository),
    inventory_repository: InventoryRepository = Depends(get_inventory_repository),
    suggestion_orchestrator: SuggestionOrchestrator = Depends(get_suggestion_orchestrator),
    ai_orchestrator: AIOrchestrator = Depends(get_ai_orchestrator),
) -> AskOrchestrator:
    return AskOrchestrator(
        customer_orchestrator, entry_repository, inventory_repository, suggestion_orchestrator, ai_orchestrator
    )


@router.post("/ask", response_model=AskResponse)
def ask(
    request: AskRequest,
    trader: Trader = Depends(get_current_trader),
    orchestrator: AskOrchestrator = Depends(get_ask_orchestrator),
) -> AskResponse:
    return orchestrator.answer(trader, request.question)
