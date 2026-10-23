from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


EntryType = Literal["sale", "credit_sale", "payment_received", "expense"]


class EntryCreate(BaseModel):
    type: EntryType
    item: str | None = Field(default=None, min_length=1, max_length=100)
    quantity: float | None = Field(default=None, gt=0)
    unit: str | None = Field(default=None, max_length=40)
    amount_ngn: int = Field(ge=0)
    customer: str | None = Field(default=None, min_length=1, max_length=120)
    due_date: str | None = Field(default=None, max_length=80)
    confidence: float | None = Field(default=None, ge=0, le=1)
    raw_text: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def require_customer_for_credit(self) -> EntryCreate:
        if self.type in {"credit_sale", "payment_received"} and not self.customer:
            raise ValueError(f"customer is required for {self.type}")
        return self


class Entry(EntryCreate):
    id: int
    cost_of_goods_ngn: int | None
    created_at: str


class CustomerBalance(BaseModel):
    name: str
    amount_owed_ngn: int
    open_credit_sales: int


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)


class MessageRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    conversation_id: str = Field(min_length=1, max_length=120)


class StockInRequest(BaseModel):
    item: str = Field(min_length=1, max_length=100)
    quantity: float = Field(gt=0)
    unit: str = Field(min_length=1, max_length=40)
    unit_cost_ngn: int = Field(ge=0)
    reorder_level: float = Field(default=0, ge=0)


class InventoryItem(BaseModel):
    id: int
    item: str
    unit: str
    quantity_on_hand: float
    unit_cost_ngn: float
    reorder_level: float
    updated_at: str


class ProfitReport(BaseModel):
    start_date: str
    end_date: str
    sales_ngn: int
    expenses_ngn: int
    cost_of_goods_ngn: int
    estimated_profit_ngn: int
    uncosted_sales_count: int
