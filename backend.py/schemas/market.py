from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field


MarketPriority = Literal["cheapest", "balanced", "reviews"]


class MarketRecommendationRequest(BaseModel):
    product: str = Field(min_length=1, max_length=80)
    quantity: float = Field(gt=0, le=100000)
    priority: MarketPriority = "balanced"
    travel_date: date | None = None


class MarketReviewCreate(BaseModel):
    market_id: str = Field(min_length=1, max_length=50)
    product: str = Field(min_length=1, max_length=80)
    reviewer_id: str = Field(min_length=3, max_length=80)
    rating: int = Field(ge=1, le=5)
    review_text: str = Field(min_length=5, max_length=600)


class CommunityReviewSummary(BaseModel):
    average_rating: float | None = None
    review_count: int = Field(ge=0)
    verified: Literal[False] = False


class MarketOffer(BaseModel):
    id: str
    product: str
    market_id: str
    market: str
    area: str
    unit: str
    unit_price_ngn: int = Field(ge=0)
    data_status: Literal["source_snapshot", "synthetic_demo"]
    source_name: str | None = None
    source_url: str | None = None
    observed_at: str | None = None
    total_cost_ngn: int = Field(ge=0)
    community_reviews: CommunityReviewSummary
    weather_forecast: dict[str, Any] | None = None
    weather_source: str | None = None
    score: float | None = None
    score_breakdown: dict[str, float | None] | None = None


class MarketRecommendationResponse(BaseModel):
    product: str
    unit: str
    requested_quantity: float
    priority: MarketPriority
    data_notice: str
    attribution: str
    attribution_url: str
    recommendation: MarketOffer | None
    ranked_offers: list[MarketOffer]
    demo_comparisons: list[MarketOffer]
    travel_date: str | None = None
    scoring_weights: dict[str, float]
    recommendation_basis: str
    weather_status: Literal["available", "unavailable"]


class MarketReviewResponse(BaseModel):
    status: Literal["saved"] = "saved"
    market_id: str
    product: str
    rating: int
    review_text: str
    verified_purchase: Literal[False] = False
    note: str


class MarketReviewItem(BaseModel):
    market_id: str
    product: str
    rating: int
    review_text: str
    created_at: str


class MarketReviewsResponse(BaseModel):
    product: str
    verified_purchase: Literal[False] = False
    reviews: list[MarketReviewItem]
    summary: dict[str, CommunityReviewSummary]


class MarketSummary(BaseModel):
    id: str
    name: str
    area: str
    data_status: Literal["source_snapshot", "synthetic_demo", "not_available"]
    source_name: str | None = None
    source_url: str | None = None
    observed_at: str | None = None
    forecast: dict[str, Any] | None = None


class MarketListResponse(BaseModel):
    data_notice: str
    products: list[str]
    weather_source: str
    weather_status: Literal["available", "unavailable"]
    markets: list[MarketSummary]
