from app.home import services
from app.home.schemas import HomeSummary, LowStockItem
from app.inventory import services as inventory_services
from app.inventory.repositories.inventory_repository import InventoryRepository
from app.ledger import services as ledger_services
from app.ledger.repositories.entry_repository import EntryRepository
from app.onboarding.models import Trader
from app.shared.periods import Period, period_start
from app.suggestions.orchestrator import SuggestionOrchestrator

RECENT_ENTRIES = 10


class HomeOrchestrator:
    def __init__(
        self,
        entry_repository: EntryRepository,
        inventory_repository: InventoryRepository,
        suggestion_orchestrator: SuggestionOrchestrator,
    ):
        self.entry_repository = entry_repository
        self.inventory_repository = inventory_repository
        self.suggestion_orchestrator = suggestion_orchestrator

    def get_summary(self, trader: Trader, period: Period) -> HomeSummary:
        since = period_start(period)
        revenue, expenses, items_logged = self.entry_repository.period_totals(trader.id, since)

        low_stock: list[LowStockItem] = []
        for item, quantity_on_hand in self.inventory_repository.list_items_with_quantity(trader.id):
            item_out = inventory_services.to_item_out(item, quantity_on_hand)
            if not item_out.low_stock:
                continue
            # No reorder quantity means nothing to rank for; no guess is made (BR-S1).
            suggestion = (
                self.suggestion_orchestrator.top_suggestion(trader, item.name, item.reorder_quantity)
                if item.reorder_quantity > 0
                else None
            )
            low_stock.append(LowStockItem(**item_out.model_dump(), top_suggestion=suggestion))

        recent = self.entry_repository.list_entries(trader.id, None, None, RECENT_ENTRIES, 0)
        return HomeSummary(
            period=period,
            period_start=since,
            revenue_ngn=revenue,
            expenses_ngn=expenses,
            profit_ngn=services.profit(revenue, expenses),
            total_owed_ngn=services.total_owed(self.entry_repository.customer_balances(trader.id).values()),
            items_logged=items_logged,
            low_stock_items=low_stock,
            recent_entries=[ledger_services.to_entry_out(entry, name) for entry, name in recent],
        )
