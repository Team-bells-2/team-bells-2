from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class OpeningItem(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    unit: str = Field(min_length=1, max_length=48)
    unit_cost_ngn: int = Field(default=0, ge=0)
    opening_quantity: float | None = Field(default=None, ge=0)
    reorder_level: float = Field(default=0, ge=0)
    reorder_quantity: float = Field(default=0, ge=0)


class OnboardingRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    phone: str = Field(min_length=7, max_length=32)
    business_name: str = Field(min_length=1, max_length=160)
    sector: str = Field(min_length=1, max_length=40)
    location_name: str = Field(min_length=1, max_length=120)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    items: list[OpeningItem] = Field(default_factory=list, max_length=40)
    pin: str = Field(pattern=r"^\d{4,6}$", description="4 to 6 digits, used with the phone number to log in.")


class LoginRequest(BaseModel):
    phone: str = Field(min_length=7, max_length=32)
    pin: str = Field(pattern=r"^\d{4,6}$")


class ChangePinRequest(BaseModel):
    current_pin: str = Field(pattern=r"^\d{4,6}$")
    new_pin: str = Field(pattern=r"^\d{4,6}$")


class OnboardingResponse(BaseModel):
    trader_id: int
    session_token: str
    token_type: str = "bearer"
    expires_at: str


class ProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    phone: str
    business_name: str
    sector: str
    location_name: str
    latitude: float | None
    longitude: float | None


class ProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    business_name: str | None = Field(default=None, min_length=1, max_length=160)
    sector: str | None = Field(default=None, min_length=1, max_length=40)
    location_name: str | None = Field(default=None, min_length=1, max_length=120)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
