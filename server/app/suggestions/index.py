from __future__ import annotations

import math

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.inventory.models import InventoryItem
from app.onboarding.models import Trader
from app.shared.Infrastructure.db.session import get_db
from app.shared.Infrastructure.llm.index import phrase_reason
from app.shared.auth import get_current_trader
from app.suggestions.config import DISTANCE_HALF_KM, MAX_SUGGESTIONS, QUALITY_SCORES, WEIGHTS
from app.suggestions.models import Supplier, SupplierOffer, SupplierReview
from app.suggestions.seed import MARKETS

router = APIRouter(prefix="/suggestions", tags=["suggestions"])


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi, d_lambda = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * radius_km * math.asin(math.sqrt(a))


def _trader_position(trader: Trader) -> tuple[float, float] | None:
    if trader.latitude is not None and trader.longitude is not None:
        return trader.latitude, trader.longitude
    location = trader.location_name.casefold()
    for market, position in MARKETS.items():
        if market.casefold() in location or market.casefold().removesuffix(" market") in location:
            return position
    return None


def _template_reason(factors: dict[str, float], facts: dict) -> str:
    top = sorted(factors, key=lambda name: (-factors[name], name))[:2]
    phrases = {
        "distance": "e near you" if facts["distance_km"] is None else "e dey your market" if facts["distance_km"] < 0.5 else f"e dey {facts['distance_km']} km away",
        "rating": f"{facts['review_count']} traders rate am {facts['average_rating']}",
        "quality": f"e get grade {facts['quality_grade']} quality",
        "cost": f"na ₦{facts['unit_price_ngn']:,} per {facts['unit']}",
        "quantity": f"e get {facts['quantity_available']:g} {facts['unit']}s for stock",
    }
    return f"Good choice: {phrases[top[0]]}, {phrases[top[1]]}."


def rank_suppliers(db: Session, trader: Trader, item: str, quantity: float | None = None, phrase: bool = True) -> dict:
    """Deterministic ranking in code (FR-S30). The model only phrases the reason (FR-S31); phrase=False keeps the template."""
    item = item.strip().casefold()
    if quantity is None:
        inventory_item = db.scalar(select(InventoryItem).where(InventoryItem.trader_id == trader.id, func.lower(InventoryItem.name) == item))
        quantity = inventory_item.reorder_quantity if inventory_item and inventory_item.reorder_quantity else 1.0

    offers = db.execute(select(SupplierOffer, Supplier).join(Supplier).where(func.lower(SupplierOffer.item) == item)).all()
    if not offers:
        return {"item": item, "quantity_needed": quantity, "demo_data": True, "suppliers": []}

    ratings = dict(db.execute(select(SupplierReview.supplier_id, func.avg(SupplierReview.rating)).group_by(SupplierReview.supplier_id)).all())
    counts = dict(db.execute(select(SupplierReview.supplier_id, func.count(SupplierReview.id)).group_by(SupplierReview.supplier_id)).all())
    position = _trader_position(trader)
    cheapest = min(offer.unit_price_ngn for offer, _ in offers)

    scored = []
    for offer, supplier in offers:
        distance = round(_distance_km(*position, supplier.latitude, supplier.longitude), 1) if position else None
        rating = round(float(ratings.get(supplier.id, 0)), 1)
        factors = {
            "distance": 1 / (1 + distance / DISTANCE_HALF_KM) if distance is not None else 0.0,
            "rating": rating / 5,
            "quality": QUALITY_SCORES.get(offer.quality_grade, 0.0),
            "cost": cheapest / offer.unit_price_ngn,
            "quantity": min(offer.quantity_available / quantity, 1.0) if quantity > 0 else 1.0,
        }
        weighted = {name: WEIGHTS[name] * value for name, value in factors.items()}
        can_fill = offer.quantity_available >= quantity
        scored.append((can_fill, sum(weighted.values()), supplier, offer, distance, rating, weighted))

    # Suppliers who can fill the quantity always rank above those who cannot; ties break on id for a stable order.
    scored.sort(key=lambda row: (not row[0], -row[1], row[2].id))
    suggestions = []
    for can_fill, score, supplier, offer, distance, rating, weighted in scored[:MAX_SUGGESTIONS]:
        facts = {
            "supplier": supplier.name, "area": supplier.area, "distance_km": distance,
            "unit_price_ngn": offer.unit_price_ngn, "unit": offer.unit, "average_rating": rating,
            "review_count": int(counts.get(supplier.id, 0)), "quality_grade": offer.quality_grade,
            "quantity_available": offer.quantity_available, "can_fill_quantity": can_fill,
        }
        suggestions.append({
            "supplier_id": supplier.id, **facts, "score": round(score, 4),
            "reason": (phrase_reason(facts) if phrase else None) or _template_reason(weighted, facts),
        })
    return {"item": item, "quantity_needed": quantity, "demo_data": True, "suppliers": suggestions}


@router.get("")
def get_suggestions(
    item: str = Query(min_length=1, max_length=120),
    quantity: float | None = Query(default=None, gt=0),
    trader: Trader = Depends(get_current_trader),
    db: Session = Depends(get_db),
) -> dict:
    return rank_suppliers(db, trader, item, quantity)
