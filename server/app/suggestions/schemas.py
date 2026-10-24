from typing import Literal

from pydantic import BaseModel

from app.shared.types import Money, Quantity


class SupplierSuggestion(BaseModel):
    """Every figure is read from the database; only `reason` is wording (FR-S31)."""

    supplier_id: int
    supplier_name: str
    area: str
    distance_km: float | None
    unit: str
    unit_price_ngn: Money
    average_rating: float | None
    review_count: int
    quality_grade: Literal["A", "B", "C"]
    quantity_available: Quantity
    can_fill: bool
    reason: str


class SuggestionsResponse(BaseModel):
    item: str
    quantity_needed: Quantity
    data_label: Literal["Demo data"] = "Demo data"
    suggestions: list[SupplierSuggestion]
