"""Synthetic supplier, offer and review data for the demo (FR-S29). Labelled as demo data in the API."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.suggestions.models import Supplier, SupplierOffer, SupplierReview

# Approximate coordinates of Lagos markets that traders pick from at onboarding.
MARKETS = {
    "Mile 12 Market": (6.6077, 3.3986),
    "Oyingbo Market": (6.4836, 3.3878),
    "Daleko Market": (6.5263, 3.3367),
    "Mushin Market": (6.5336, 3.3502),
    "Ikotun Market": (6.5497, 3.2672),
    "Oshodi Market": (6.5546, 3.3436),
    "Balogun Market": (6.4549, 3.3887),
    "Ketu Market": (6.5976, 3.3896),
    "Ajah Market": (6.4682, 3.5694),
    "Agege Market": (6.6180, 3.3209),
}

SUPPLIERS = [
    {
        "name": "Alhaji Musa Rice Depot", "area": "Mile 12 Market",
        "offers": [("rice", "bag", 58000, 120, "A"), ("beans", "bag", 71000, 40, "B"), ("garri", "bag", 26000, 60, "B")],
        "reviews": [(5, "Bags are full weight, no stones."), (4, "Good price when you buy plenty."), (5, "Delivers to Mushin same day.")],
    },
    {
        "name": "Iya Basira Foodstuff", "area": "Oyingbo Market",
        "offers": [("rice", "bag", 61000, 25, "A"), ("beans", "bag", 69000, 30, "A"), ("oil", "keg", 38000, 20, "B")],
        "reviews": [(5, "Honest woman, clean beans."), (4, "Sometimes runs out early."), (4, "Fair price for the quality.")],
    },
    {
        "name": "Daleko Grains Hub", "area": "Daleko Market",
        "offers": [("rice", "bag", 55500, 8, "B"), ("beans", "bag", 66000, 50, "C"), ("garri", "bag", 24500, 80, "C")],
        "reviews": [(3, "Cheap but check the bags."), (4, "Plenty stock of beans."), (3, "Rice had some broken grains.")],
    },
    {
        "name": "Mushin Wholesale Store", "area": "Mushin Market",
        "offers": [("rice", "bag", 59500, 60, "B"), ("garri", "bag", 27000, 45, "A"), ("oil", "keg", 36500, 35, "A")],
        "reviews": [(4, "Close to my shop, quick service."), (5, "Oil is pure, not mixed."), (4, "Garri is dry and clean.")],
    },
    {
        "name": "Ikotun Beans & Garri", "area": "Ikotun Market",
        "offers": [("beans", "bag", 67500, 70, "B"), ("garri", "bag", 23500, 100, "B")],
        "reviews": [(4, "Best garri price around."), (3, "Long queue on Saturdays."), (4, "Beans was good, small weevils.")],
    },
    {
        "name": "Oshodi Oil Mart", "area": "Oshodi Market",
        "offers": [("oil", "keg", 35000, 50, "B"), ("rice", "bag", 60500, 15, "B")],
        "reviews": [(4, "Good oil price."), (4, "They give receipt."), (3, "Parking is hard.")],
    },
    {
        "name": "Ketu Farm Fresh", "area": "Ketu Market",
        "offers": [("beans", "bag", 72000, 20, "A"), ("oil", "keg", 39500, 15, "A"), ("garri", "bag", 28000, 30, "A")],
        "reviews": [(5, "Top quality, a bit costly."), (5, "Garri straight from Ijebu."), (4, "Friendly sellers.")],
    },
    {
        "name": "Agege Bulk Supplies", "area": "Agege Market",
        "offers": [("rice", "bag", 57000, 200, "B"), ("oil", "keg", 37000, 60, "C")],
        "reviews": [(4, "Always have stock."), (3, "Oil quality varies."), (4, "Good for big orders.")],
    },
]


def seed_suppliers(db: Session) -> None:
    if db.scalar(select(func.count(Supplier.id))):
        return
    for data in SUPPLIERS:
        latitude, longitude = MARKETS[data["area"]]
        supplier = Supplier(name=data["name"], area=data["area"], latitude=latitude, longitude=longitude)
        db.add(supplier)
        db.flush()
        for item, unit, price, quantity, grade in data["offers"]:
            db.add(SupplierOffer(supplier_id=supplier.id, item=item, unit=unit, unit_price_ngn=price, quantity_available=quantity, quality_grade=grade))
        for rating, comment in data["reviews"]:
            db.add(SupplierReview(supplier_id=supplier.id, rating=rating, comment=comment))
