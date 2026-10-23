from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

EntryType = Literal["sale", "credit_sale", "payment_received", "expense"]


class Interpretation(BaseModel):
    """The only shape model output may take. There is no amount figure and no stock action:
    the model quotes the amount phrase and code parses it (FR-S4); stock only changes
    through ledger rules (NFR-1). Unknown keys from the model are dropped."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    intent: Literal["entry", "correction", "unknown"]
    type: EntryType | None = None
    item: str | None = Field(default=None, max_length=100)
    quantity: Decimal | None = Field(default=None, gt=0)
    unit: str | None = Field(default=None, max_length=40)
    amount_text: str | None = Field(default=None, max_length=80)
    customer: str | None = Field(default=None, max_length=120)
    due_date: date | None = None
    confidence: float = Field(ge=0, le=1)
    question: str | None = Field(default=None, max_length=200)


class ReasonFacts(BaseModel):
    """Facts about one ranked supplier, computed in code, for the model to phrase."""

    supplier_name: str
    distance_km: float | None
    unit_price_ngn: float
    average_rating: float | None
    quality_grade: str
    can_fill: bool
    strongest_factors: list[str]


class PhrasedReasons(BaseModel):
    model_config = ConfigDict(extra="ignore")

    reasons: list[str] = Field(max_length=10)
