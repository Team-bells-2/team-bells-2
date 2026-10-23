from decimal import Decimal

from app.ai.orchestrator import AIOrchestrator
from app.ai.schemas import ReasonFacts
from app.inventory.repositories.inventory_repository import InventoryRepository
from app.onboarding.models import Trader
from app.shared.errors import AppError
from app.suggestions import services
from app.suggestions.repositories.supplier_repository import SupplierRepository
from app.suggestions.schemas import SuggestionsResponse, SupplierSuggestion

MAX_SUGGESTIONS = 3


class SuggestionOrchestrator:
    def __init__(
        self,
        supplier_repository: SupplierRepository,
        inventory_repository: InventoryRepository,
        ai_orchestrator: AIOrchestrator,
        weights: services.RankingWeights,
    ):
        self.supplier_repository = supplier_repository
        self.inventory_repository = inventory_repository
        self.ai_orchestrator = ai_orchestrator
        self.weights = weights

    def get_suggestions(self, trader: Trader, item: str, quantity: Decimal | None) -> SuggestionsResponse:
        """Up to 3 suppliers for an item, ranked in code; the model only words the reasons (FR-S30, S31)."""
        quantity_needed = quantity if quantity is not None else self._default_quantity(trader.id, item)

        candidates = [
            services.Candidate(
                supplier_id=supplier.id,
                supplier_name=supplier.name,
                area=supplier.area,
                latitude=supplier.latitude,
                longitude=supplier.longitude,
                unit=offer.unit,
                unit_price_ngn=offer.unit_price_ngn,
                quantity_available=offer.quantity_available,
                quality_grade=offer.quality_grade,
                average_rating=float(average) if average is not None else None,
                review_count=count or 0,
            )
            for offer, supplier, average, count in self.supplier_repository.list_offers_for_item(item)
        ]
        origin = (
            (trader.latitude, trader.longitude)
            if trader.latitude is not None and trader.longitude is not None
            else None
        )
        top = services.rank_candidates(candidates, origin, quantity_needed, self.weights)[:MAX_SUGGESTIONS]

        facts = [
            ReasonFacts(
                supplier_name=s.candidate.supplier_name,
                distance_km=s.distance_km,
                unit_price_ngn=float(s.candidate.unit_price_ngn),
                average_rating=s.candidate.average_rating,
                quality_grade=s.candidate.quality_grade,
                can_fill=s.can_fill,
                strongest_factors=services.strongest_factors(s),
            )
            for s in top
        ]
        reasons = self.ai_orchestrator.phrase_reasons(facts) or [services.template_reason(s) for s in top]

        return SuggestionsResponse(
            item=item,
            quantity_needed=quantity_needed,
            suggestions=[
                SupplierSuggestion(
                    supplier_id=s.candidate.supplier_id,
                    supplier_name=s.candidate.supplier_name,
                    area=s.candidate.area,
                    distance_km=s.distance_km,
                    unit=s.candidate.unit,
                    unit_price_ngn=s.candidate.unit_price_ngn,
                    average_rating=round(s.candidate.average_rating, 2) if s.candidate.average_rating else None,
                    review_count=s.candidate.review_count,
                    quality_grade=s.candidate.quality_grade,  # pyright: ignore[reportArgumentType]  (DB check constraint)
                    quantity_available=s.candidate.quantity_available,
                    can_fill=s.can_fill,
                    reason=reason,
                )
                for s, reason in zip(top, reasons)
            ],
        )

    def _default_quantity(self, trader_id: int, item: str) -> Decimal:
        """Quantity defaults to the item's reorder quantity (FR-S30)."""
        inventory_item = self.inventory_repository.get_item_by_name(trader_id, item)
        if inventory_item is None or inventory_item.reorder_quantity <= 0:
            raise AppError(422, "quantity_required", f"How many {item} do you need? Add a quantity.")
        return inventory_item.reorder_quantity
