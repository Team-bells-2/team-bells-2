import math
from dataclasses import dataclass
from decimal import Decimal

# Below this distance a supplier is described as "in your market".
_SAME_MARKET_KM = 0.5


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


def _naira(amount: Decimal) -> str:
    return f"₦{amount:,.0f}" if amount == amount.to_integral_value() else f"₦{amount:,.2f}"


def _factor_phrase(name: str, scored: ScoredCandidate) -> str:
    """One factor in words, quoting its figure from the database (BR-S2)."""
    candidate = scored.candidate
    if name == "distance":
        if scored.distance_km is None:
            return "distance no clear"
        return "e dey your market" if scored.distance_km < _SAME_MARKET_KM else f"e dey {scored.distance_km:g} km away"
    if name == "rating":
        if candidate.average_rating is None:
            return "no review yet"
        return f"{candidate.review_count} traders rate am {candidate.average_rating:.1f}"
    if name == "quality":
        return f"e get grade {candidate.quality_grade} quality"
    if name == "cost":
        return f"na {_naira(candidate.unit_price_ngn)} per {candidate.unit}"
    available = candidate.quantity_available.normalize()
    unit = candidate.unit if available == 1 or candidate.unit.endswith("s") else f"{candidate.unit}s"
    return f"e get {available:f} {unit} for stock"


def template_reason(scored: ScoredCandidate) -> str:
    """Wording used on Home and whenever the model call fails (FR-S31): the two strongest factors."""
    first, second = (_factor_phrase(name, scored) for name in strongest_factors(scored))
    reason = f"Recommended: {first}, {second}."
    if not scored.can_fill:
        reason += " E no fit cover your full quantity."
    return reason
