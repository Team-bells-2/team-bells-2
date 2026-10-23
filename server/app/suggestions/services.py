import math
from dataclasses import dataclass
from decimal import Decimal

_FACTOR_PHRASES: dict[str, str] = {
    "distance": "close to you",
    "rating": "well reviewed by other traders",
    "quality": "good quality",
    "cost": "good price",
    "quantity": "enough stock for your order",
}


@dataclass(frozen=True)
class RankingWeights:
    distance: float
    rating: float
    quality: float
    cost: float
    quantity: float
    distance_half_km: float
    quality_scores: dict[str, float]


@dataclass(frozen=True)
class Candidate:
    supplier_id: int
    supplier_name: str
    area: str
    latitude: float
    longitude: float
    unit: str
    unit_price_ngn: Decimal
    quantity_available: Decimal
    quality_grade: str
    average_rating: float | None
    review_count: int


@dataclass(frozen=True)
class ScoredCandidate:
    candidate: Candidate
    distance_km: float | None
    can_fill: bool
    contributions: dict[str, float]
    score: float


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * radius_km * math.asin(math.sqrt(a))


def rank_candidates(
    candidates: list[Candidate],
    origin: tuple[float, float] | None,
    quantity_needed: Decimal,
    weights: RankingWeights,
) -> list[ScoredCandidate]:
    """Deterministic ranking from five factors (FR-S30). Each factor score rises as the factor
    improves, so improving one factor never lowers a supplier's rank. Suppliers that can fill
    the quantity always rank above those that cannot. Ties break on distance, then supplier id."""
    if not candidates:
        return []
    cheapest = min(candidate.unit_price_ngn for candidate in candidates)
    scored: list[ScoredCandidate] = []
    for candidate in candidates:
        distance = (
            haversine_km(origin[0], origin[1], candidate.latitude, candidate.longitude) if origin else None
        )
        factors = {
            "distance": weights.distance_half_km / (weights.distance_half_km + distance) if distance is not None else 0.0,
            "rating": (candidate.average_rating or 0.0) / 5,
            "quality": weights.quality_scores[candidate.quality_grade],
            "cost": float(cheapest / candidate.unit_price_ngn) if candidate.unit_price_ngn > 0 else 1.0,
            "quantity": min(1.0, float(candidate.quantity_available / quantity_needed)),
        }
        contributions = {name: getattr(weights, name) * value for name, value in factors.items()}
        scored.append(
            ScoredCandidate(
                candidate=candidate,
                distance_km=round(distance, 1) if distance is not None else None,
                can_fill=candidate.quantity_available >= quantity_needed,
                contributions=contributions,
                score=sum(contributions.values()),
            )
        )
    return sorted(
        scored,
        key=lambda s: (
            not s.can_fill,
            -s.score,
            s.distance_km if s.distance_km is not None else math.inf,
            s.candidate.supplier_id,
        ),
    )


def strongest_factors(scored: ScoredCandidate, count: int = 2) -> list[str]:
    ordered = sorted(scored.contributions.items(), key=lambda item: (-item[1], item[0]))
    return [name for name, _ in ordered[:count]]


def template_reason(scored: ScoredCandidate) -> str:
    """Fallback wording when the model call fails (FR-S31)."""
    phrases = [_FACTOR_PHRASES[name] for name in strongest_factors(scored)]
    reason = f"{phrases[0].capitalize()} and {phrases[1]}."
    if not scored.can_fill:
        reason += " Cannot fill your full quantity."
    return reason
