from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.shared.types import Money

Scope = Literal["sales_total", "active_days", "total_owed"]
RequestStatus = Literal["pending", "approved", "rejected", "revoked"]


class AccessRequestCreate(BaseModel):
    """From the lender agent (FR-S13). Purpose and at least one scope are required (422 otherwise)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    trader_phone: str = Field(min_length=7, max_length=20)
    agent_name: str = Field(min_length=1, max_length=120)
    purpose: str = Field(min_length=3, max_length=500)
    data_scopes: list[Scope] = Field(min_length=1)

    @field_validator("data_scopes")
    @classmethod
    def unique_scopes(cls, scopes: list[Scope]) -> list[Scope]:
        return list(dict.fromkeys(scopes))


class AccessRequestCreated(BaseModel):
    request_id: int
    status: RequestStatus
    # Shown once. The agent sends it as X-Claim-Secret to poll for the decision (BR-K1, BR-K2).
    claim_secret: str


class AccessRequestStatus(BaseModel):
    """What the agent sees when it polls. access_token appears exactly once, after approval."""

    request_id: int
    status: RequestStatus
    scopes: list[Scope]
    access_token: str | None = None
    token_type: Literal["bearer"] | None = None
    expires_at: datetime | None = None
    token_already_collected: bool | None = None


class AccessLogOut(BaseModel):
    endpoint: str
    result: str
    at: datetime


class AccessRequestOut(BaseModel):
    """For the trader's app: the consent prompt and the access log (FR-C3, FR-C16)."""

    id: int
    agent_name: str
    purpose: str
    scopes: list[Scope]
    status: RequestStatus
    requested_at: datetime
    decided_at: datetime | None
    expires_at: datetime | None
    prompt: str
    log: list[AccessLogOut]


class AccessDecision(BaseModel):
    approve: bool


class AgentSummary(BaseModel):
    """Allow-list response (FR-S15): totals only. No customer names, raw text, entry IDs, phone or
    location. Only the approved scopes are present."""

    period_days: int
    generated_at: datetime
    scopes: list[Scope]
    sales_total_ngn: Money | None = None
    active_days: int | None = None
    total_owed_ngn: Money | None = None
