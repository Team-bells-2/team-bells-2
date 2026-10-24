from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OnboardingItem(BaseModel):
    """A main item the trader sells; becomes an inventory item, with opening stock if given (FR-S21)."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    unit: str = Field(min_length=1, max_length=40)
    unit_cost_ngn: Decimal | None = Field(default=None, ge=0)
    opening_quantity: Decimal | None = Field(default=None, gt=0)
    reorder_level: Decimal = Field(default=Decimal(0), ge=0)
    reorder_quantity: Decimal = Field(default=Decimal(0), ge=0)


class OnboardingRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=120)
    phone: str = Field(min_length=7, max_length=20)
    business_name: str = Field(min_length=1, max_length=160)
    sector: str = Field(min_length=1, max_length=40)
    location_name: str = Field(min_length=1, max_length=120)
    items: list[OnboardingItem] = Field(default_factory=list, max_length=40)

    @field_validator("items")
    @classmethod
    def unique_item_names(cls, items: list[OnboardingItem]) -> list[OnboardingItem]:
        names = [item.name.lower() for item in items]
        if len(names) != len(set(names)):
            raise ValueError("each item name must appear once")
        return items


class TraderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    phone: str
    business_name: str
    sector: str
    location_name: str
    latitude: float | None
    longitude: float | None
    created_at: datetime


class OnboardingResponse(BaseModel):
    token: str
    trader: TraderOut
