from datetime import datetime

from pydantic import BaseModel

from app.inventory.schemas import InventoryItemOut
from app.shared.periods import Period
from app.shared.types import Money


class HomeSummary(BaseModel):
    period: Period
    period_start: datetime
    revenue_ngn: Money
    expenses_ngn: Money
    profit_ngn: Money
    total_owed_ngn: Money
    items_logged: int
    low_stock_items: list[InventoryItemOut]
