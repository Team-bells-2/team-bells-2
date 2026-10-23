from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class OnboardingRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=120)
    phone: str = Field(min_length=7, max_length=20)
    business_name: str = Field(min_length=1, max_length=160)
    sector: str = Field(min_length=1, max_length=40)
    location_name: str = Field(min_length=1, max_length=120)


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
