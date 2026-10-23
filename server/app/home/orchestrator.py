from app.home import services
from app.home.schemas import HomeSummary
from app.inventory import services as inventory_services
from app.inventory.repositories.inventory_repository import InventoryRepository
from app.ledger.repositories.entry_repository import EntryRepository
from app.shared.periods import Period, period_start


class HomeOrchestrator:
    def __init__(self, entry_repository: EntryRepository, inventory_repository: InventoryRepository):
        self.entry_repository = entry_repository
        self.inventory_repository = inventory_repository

    def get_summary(self, trader_id: int, period: Period) -> HomeSummary:
        since = period_start(period)
        revenue, expenses, items_logged = self.entry_repository.period_totals(trader_id, since)
        items = [
            inventory_services.to_item_out(item, quantity_on_hand)
            for item, quantity_on_hand in self.inventory_repository.list_items_with_quantity(trader_id)
        ]
        return HomeSummary(
            period=period,
            period_start=since,
            revenue_ngn=revenue,
            expenses_ngn=expenses,
            profit_ngn=services.profit(revenue, expenses),
            total_owed_ngn=services.total_owed(self.entry_repository.customer_balances(trader_id).values()),
            items_logged=items_logged,
            low_stock_items=[item for item in items if item.low_stock],
        )
