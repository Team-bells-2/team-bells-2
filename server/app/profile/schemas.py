from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProfileOut(BaseModel):
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


class ProfileUpdate(BaseModel):
    """FR-S22: only these fields are editable. Omitted fields are left unchanged."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    business_name: str | None = Field(default=None, min_length=1, max_length=160)
    sector: str | None = Field(default=None, min_length=1, max_length=40)
    location_name: str | None = Field(default=None, min_length=1, max_length=120)
