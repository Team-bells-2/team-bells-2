from typing import Literal

from pydantic import BaseModel


class SeedSummary(BaseModel):
    locations_added: int
    suppliers_added: int
    offers_added: int
    reviews_added: int


class ResetResult(BaseModel):
    status: Literal["reset"] = "reset"
    reference_data: SeedSummary


class DemoSeedResult(BaseModel):
    """The demo trader's session token, for the judges' dashboard (D4) and the app."""

    status: Literal["seeded"] = "seeded"
    trader_id: int
    phone: str
    pin: str
    token: str
    token_type: Literal["bearer"] = "bearer"
