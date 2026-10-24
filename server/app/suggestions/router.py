from decimal import Decimal

from fastapi import APIRouter, Depends, Query

from app.ai.dependencies import get_ai_orchestrator
from app.ai.orchestrator import AIOrchestrator
from app.inventory.dependencies import get_inventory_repository
from app.inventory.repositories.inventory_repository import InventoryRepository
from app.onboarding.models import Trader
from app.onboarding.router import get_current_trader
from app.shared.env import settings
from app.suggestions.dependencies import get_supplier_repository
from app.suggestions.orchestrator import SuggestionOrchestrator
from app.suggestions.repositories.supplier_repository import SupplierRepository
from app.suggestions.schemas import SuggestionsResponse
from app.suggestions.services import RankingWeights

router = APIRouter(tags=["suggestions"])


def get_suggestion_orchestrator(
    supplier_repository: SupplierRepository = Depends(get_supplier_repository),
    inventory_repository: InventoryRepository = Depends(get_inventory_repository),
    ai_orchestrator: AIOrchestrator = Depends(get_ai_orchestrator),
) -> SuggestionOrchestrator:
    weights = RankingWeights(
        distance=settings.SUGGESTION_WEIGHT_DISTANCE,
        rating=settings.SUGGESTION_WEIGHT_RATING,
        quality=settings.SUGGESTION_WEIGHT_QUALITY,
        cost=settings.SUGGESTION_WEIGHT_COST,
        quantity=settings.SUGGESTION_WEIGHT_QUANTITY,
        distance_half_km=settings.SUGGESTION_DISTANCE_HALF_KM,
        quality_scores={
            "A": settings.SUGGESTION_QUALITY_SCORE_A,
            "B": settings.SUGGESTION_QUALITY_SCORE_B,
            "C": settings.SUGGESTION_QUALITY_SCORE_C,
        },
    )
    return SuggestionOrchestrator(supplier_repository, inventory_repository, ai_orchestrator, weights)


@router.get("/suggestions", response_model=SuggestionsResponse)
def get_suggestions(
    item: str = Query(min_length=1, max_length=100),
    quantity: Decimal | None = Query(default=None, gt=0),
    trader: Trader = Depends(get_current_trader),
    orchestrator: SuggestionOrchestrator = Depends(get_suggestion_orchestrator),
) -> SuggestionsResponse:
    return orchestrator.get_suggestions(trader, item, quantity)
