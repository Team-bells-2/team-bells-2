from datetime import datetime

from pydantic import BaseModel

from app.inventory.schemas import InventoryItemOut
from app.ledger.schemas import EntryOut
from app.shared.periods import Period
from app.shared.types import Money
from app.suggestions.schemas import SupplierSuggestion


class LowStockItem(InventoryItemOut):
    # The first-ranked restock supplier (FR-S32). None when the item has no reorder quantity
    # to rank for, or no supplier offers it.
    top_suggestion: SupplierSuggestion | None


class HomeSummary(BaseModel):
    period: Period
    period_start: datetime
    revenue_ngn: Money
    expenses_ngn: Money
    profit_ngn: Money
    total_owed_ngn: Money
    items_logged: int
    low_stock_items: list[LowStockItem]
    # The newest entries, whatever the period (FR-C13 "Items logged").
    recent_entries: list[EntryOut]
