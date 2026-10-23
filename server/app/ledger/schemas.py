from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

EntryType = Literal["sale", "credit_sale", "payment_received", "expense"]


class MessageRequest(BaseModel):
    text: str | None = Field(default=None, min_length=1, max_length=4000)
    client_message_id: str = Field(min_length=8, max_length=120)


class EntryData(BaseModel):
    type: EntryType
    item: str | None = Field(default=None, max_length=120)
    quantity: float | None = Field(default=None, gt=0)
    unit: str | None = Field(default=None, max_length=48)
    amount_ngn: int | None = Field(default=None, ge=0)
    customer: str | None = Field(default=None, max_length=120)
    due_date: date | None = None
    confidence: float = Field(ge=0, le=1)


class EntryResponse(BaseModel):
    id: int
    type: EntryType
    item: str | None
    quantity: float | None
    unit: str | None
    amount_ngn: int
    customer: str | None
    due_date: date | None
    confidence: float | None
    status: str
    stock_warning: str | None
    raw_text: str
    created_at: datetime


class MessageResponse(BaseModel):
    status: Literal["saved", "clarify", "fallback"]
    confirmation: str | None = None
    question: str | None = None
    entry: EntryResponse | None = None
    updated: bool = False


class EntriesResponse(BaseModel):
    items: list[EntryResponse]
    limit: int
    offset: int
    total: int
