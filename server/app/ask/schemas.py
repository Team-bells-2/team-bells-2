from pydantic import BaseModel, ConfigDict, Field

from app.ai.schemas import AskIntent
from app.inventory.schemas import InventoryItemOut
from app.shared.types import Money
from app.suggestions.schemas import SuggestionsResponse


class AskRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    question: str = Field(min_length=1, max_length=500)


class OwingCustomer(BaseModel):
    name: str
    balance_ngn: Money
    overdue: bool


class AskResponse(BaseModel):
    """`answer` is built in code from database figures (FR-S11). The structured field for the
    intent is set; the others are null."""

    intent: AskIntent
    answer: str
    customers: list[OwingCustomer] | None = None  # who_owes, customer_balance
    sales_ngn: Money | None = None  # today_total
    stock: InventoryItemOut | None = None  # stock_level
    suggestions: SuggestionsResponse | None = None  # restock_suggestion
