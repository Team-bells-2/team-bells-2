from __future__ import annotations

from typing import Any, Literal

Priority = Literal["cheapest", "balanced", "reviews"]

DATA_NOTICE = (
    "Ajah and Century prices are public ArketData observations dated 14 October 2026. "
    "Mile 12 prices are synthetic demo examples, not market facts. Stock availability is not provided."
)
ARKETDATA_LICENSE = "CC BY 4.0; attribution required. Include unit and observation date."
ARKETDATA_ABOUT_URL = "https://arketdata.com/about"

MARKETS: dict[str, dict[str, Any]] = {
    "mile-12": {
        "name": "Mile 12 Market",
        "area": "Ketu, Lagos",
        "data_status": "synthetic_demo",
        "source_name": "OJA demo data",
        "source_url": None,
        "observed_at": None,
    },
    "agege": {
        "name": "Agege Market",
        "area": "Agege, Lagos",
        "data_status": "not_available",
        "source_name": None,
        "source_url": None,
        "observed_at": None,
    },
    "balogun": {
        "name": "Balogun Market",
        "area": "Lagos Island, Lagos",
        "data_status": "not_available",
        "source_name": None,
        "source_url": None,
        "observed_at": None,
    },
    "ajah": {
        "name": "Ajah Market",
        "area": "Ajah, Lagos",
        "data_status": "source_snapshot",
        "source_name": "ArketData",
        "source_url": "https://arketdata.com/markets/ajah-market-lagos-12c58dd66c53",
        "observed_at": "2026-10-14",
    },
    "century": {
        "name": "Century Market",
        "area": "Lagos, Lagos",
        "data_status": "source_snapshot",
        "source_name": "ArketData",
        "source_url": "https://arketdata.com/markets/century-market-lagos-77ec819b101a",
        "observed_at": "2026-10-14",
    },
}

OFFERS: list[dict[str, Any]] = [
    {
        "id": "foreign-rice-ajah-2026-10-14", "product": "foreign rice", "market_id": "ajah",
        "unit": "50 kg bag", "unit_price_ngn": 65000,
    },
    {
        "id": "foreign-rice-century-2026-10-14", "product": "foreign rice", "market_id": "century",
        "unit": "50 kg bag", "unit_price_ngn": 50000,
    },
    {
        "id": "foreign-rice-mile12-demo", "product": "foreign rice", "market_id": "mile-12",
        "unit": "50 kg bag", "unit_price_ngn": 62000,
    },
    {
        "id": "tomato-round-ajah-2026-10-14", "product": "tomato round", "market_id": "ajah",
        "unit": "painter", "unit_price_ngn": 9000,
    },
    {
        "id": "tomato-round-century-2026-10-14", "product": "tomato round", "market_id": "century",
        "unit": "painter", "unit_price_ngn": 9000,
    },
    {
        "id": "tomato-round-mile12-demo", "product": "tomato round", "market_id": "mile-12",
        "unit": "painter", "unit_price_ngn": 8500,
    },
    {
        "id": "palm-oil-ajah-2026-10-14", "product": "palm oil", "market_id": "ajah",
        "unit": "5 litre container", "unit_price_ngn": 19000,
    },
    {
        "id": "palm-oil-century-2026-10-14", "product": "palm oil", "market_id": "century",
        "unit": "5 litre container", "unit_price_ngn": 14000,
    },
    {
        "id": "palm-oil-mile12-demo", "product": "palm oil", "market_id": "mile-12",
        "unit": "5 litre container", "unit_price_ngn": 17500,
    },
    {
        "id": "beans-oloyin-ajah-2026-10-14", "product": "beans oloyin", "market_id": "ajah",
        "unit": "painter", "unit_price_ngn": 5500,
    },
    {
        "id": "beans-oloyin-century-2026-10-14", "product": "beans oloyin", "market_id": "century",
        "unit": "painter", "unit_price_ngn": 6500,
    },
    {
        "id": "beans-oloyin-mile12-demo", "product": "beans oloyin", "market_id": "mile-12",
        "unit": "painter", "unit_price_ngn": 6000,
    },
    {
        "id": "brown-beans-ajah-2026-10-14", "product": "brown beans", "market_id": "ajah",
        "unit": "painter", "unit_price_ngn": 5000,
    },
    {
        "id": "brown-beans-century-2026-10-14", "product": "brown beans", "market_id": "century",
        "unit": "painter", "unit_price_ngn": 6000,
    },
    {
        "id": "brown-beans-mile12-demo", "product": "brown beans", "market_id": "mile-12",
        "unit": "painter", "unit_price_ngn": 5500,
    },
    {
        "id": "white-beans-ajah-2026-10-14", "product": "white beans", "market_id": "ajah",
        "unit": "painter", "unit_price_ngn": 5000,
    },
    {
        "id": "white-beans-century-2026-10-14", "product": "white beans", "market_id": "century",
        "unit": "painter", "unit_price_ngn": 6000,
    },
    {
        "id": "white-beans-mile12-demo", "product": "white beans", "market_id": "mile-12",
        "unit": "painter", "unit_price_ngn": 5500,
    },
    {
        "id": "yellow-maize-ajah-2026-10-14", "product": "yellow maize", "market_id": "ajah",
        "unit": "painter", "unit_price_ngn": 2500,
    },
    {
        "id": "yellow-maize-century-2026-10-14", "product": "yellow maize", "market_id": "century",
        "unit": "painter", "unit_price_ngn": 2000,
    },
    {
        "id": "yellow-maize-mile12-demo", "product": "yellow maize", "market_id": "mile-12",
        "unit": "painter", "unit_price_ngn": 2300,
    },
    {
        "id": "white-maize-ajah-2026-10-14", "product": "white maize", "market_id": "ajah",
        "unit": "painter", "unit_price_ngn": 2500,
    },
    {
        "id": "white-maize-century-2026-10-14", "product": "white maize", "market_id": "century",
        "unit": "painter", "unit_price_ngn": 2000,
    },
    {
        "id": "white-maize-mile12-demo", "product": "white maize", "market_id": "mile-12",
        "unit": "painter", "unit_price_ngn": 2300,
    },
    {
        "id": "millet-ajah-2026-10-14", "product": "millet", "market_id": "ajah",
        "unit": "painter", "unit_price_ngn": 2500,
    },
    {
        "id": "millet-century-2026-10-14", "product": "millet", "market_id": "century",
        "unit": "painter", "unit_price_ngn": 2000,
    },
    {
        "id": "millet-mile12-demo", "product": "millet", "market_id": "mile-12",
        "unit": "painter", "unit_price_ngn": 2300,
    },
    {
        "id": "yellow-garri-ajah-2026-10-14", "product": "yellow garri", "market_id": "ajah",
        "unit": "painter", "unit_price_ngn": 2000,
    },
    {
        "id": "yellow-garri-century-2026-10-14", "product": "yellow garri", "market_id": "century",
        "unit": "painter", "unit_price_ngn": 1800,
    },
    {
        "id": "yellow-garri-mile12-demo", "product": "yellow garri", "market_id": "mile-12",
        "unit": "painter", "unit_price_ngn": 1900,
    },
    {
        "id": "white-garri-ajah-2026-10-14", "product": "white garri", "market_id": "ajah",
        "unit": "painter", "unit_price_ngn": 1500,
    },
    {
        "id": "white-garri-century-2026-10-14", "product": "white garri", "market_id": "century",
        "unit": "painter", "unit_price_ngn": 1500,
    },
    {
        "id": "white-garri-mile12-demo", "product": "white garri", "market_id": "mile-12",
        "unit": "painter", "unit_price_ngn": 1600,
    },
    {
        "id": "onion-brown-ajah-2026-10-14", "product": "onion brown", "market_id": "ajah",
        "unit": "painter", "unit_price_ngn": 7000,
    },
    {
        "id": "onion-brown-century-2026-10-14", "product": "onion brown", "market_id": "century",
        "unit": "painter", "unit_price_ngn": 12000,
    },
    {
        "id": "onion-brown-mile12-demo", "product": "onion brown", "market_id": "mile-12",
        "unit": "painter", "unit_price_ngn": 9000,
    },
    {
        "id": "egg-ajah-2026-10-14", "product": "egg", "market_id": "ajah",
        "unit": "piece", "unit_price_ngn": 250,
    },
    {
        "id": "egg-century-2026-10-14", "product": "egg", "market_id": "century",
        "unit": "piece", "unit_price_ngn": 250,
    },
    {
        "id": "egg-mile12-demo", "product": "egg", "market_id": "mile-12",
        "unit": "piece", "unit_price_ngn": 275,
    },
    {
        "id": "vegetable-oil-ajah-2026-10-14", "product": "vegetable oil", "market_id": "ajah",
        "unit": "5 litre container", "unit_price_ngn": 17000,
    },
    {
        "id": "vegetable-oil-century-2026-10-14", "product": "vegetable oil", "market_id": "century",
        "unit": "5 litre container", "unit_price_ngn": 14000,
    },
    {
        "id": "vegetable-oil-mile12-demo", "product": "vegetable oil", "market_id": "mile-12",
        "unit": "5 litre container", "unit_price_ngn": 15500,
    },
]

def available_products() -> list[str]:
    return sorted({offer["product"] for offer in OFFERS})


PRIORITY_WEIGHTS: dict[Priority, dict[str, float]] = {
    "cheapest": {"price": 0.70, "reviews": 0.15, "weather": 0.15},
    "balanced": {"price": 0.50, "reviews": 0.30, "weather": 0.20},
    "reviews": {"price": 0.30, "reviews": 0.50, "weather": 0.20},
}


def recommend_market(
    product: str,
    quantity: float,
    priority: Priority = "balanced",
    review_summaries: dict[str, dict[str, float | int]] | None = None,
    forecasts: dict[str, dict[str, Any]] | None = None,
    travel_date: str | None = None,
) -> dict[str, Any]:
    normalized_product = " ".join(product.casefold().split())
    matching = [offer for offer in OFFERS if offer["product"].casefold() == normalized_product]
    if not matching:
        return {"product": product, "requested_quantity": quantity, "priority": priority, "recommendation": None, "ranked_offers": []}

    normalized_units = {offer["unit"] for offer in matching}
    if len(normalized_units) != 1:
        raise ValueError("Market offers cannot be compared because their units differ.")
    matching.sort(key=lambda offer: offer["unit_price_ngn"])
    sourced_offers = [offer for offer in matching if MARKETS[offer["market_id"]]["data_status"] == "source_snapshot"]
    demo_offers = [offer for offer in matching if MARKETS[offer["market_id"]]["data_status"] != "source_snapshot"]
    lowest_sourced_price = min((offer["unit_price_ngn"] for offer in sourced_offers), default=None)
    weights = PRIORITY_WEIGHTS[priority]
    ranked_offers = []
    review_summaries = review_summaries or {}
    forecasts = forecasts or {}

    for offer in sourced_offers:
        market = MARKETS[offer["market_id"]]
        review = review_summaries.get(f"{offer['market_id']}:{offer['product']}", {})
        review_count = int(review.get("review_count", 0))
        average_rating = float(review.get("average_rating", 3.0))
        # Shrink low-volume ratings toward neutral so a single rating cannot dominate.
        smoothed_rating = ((average_rating * review_count) + (3.0 * 3)) / (review_count + 3)
        forecast = forecasts.get(offer["market_id"], {})
        day_forecast = next(
            (day for day in forecast.get("forecast_days", []) if day.get("date") == travel_date),
            None,
        ) if travel_date else None
        rain_score = day_forecast.get("rain_score") if day_forecast else None
        factor_values = {
            "price": lowest_sourced_price / offer["unit_price_ngn"] if lowest_sourced_price else 0.0,
            "reviews": smoothed_rating / 5,
            "weather": rain_score if rain_score is not None else 0.5,
        }
        score = sum(weights[factor] * value for factor, value in factor_values.items()) * 100
        ranked_offers.append({
            **offer,
            "market": market["name"],
            "area": market["area"],
            "data_status": market["data_status"],
            "source_name": market["source_name"],
            "source_url": market["source_url"],
            "observed_at": market["observed_at"],
            "total_cost_ngn": round(offer["unit_price_ngn"] * quantity),
            "community_reviews": {
                "average_rating": round(average_rating, 2) if review_count else None,
                "review_count": review_count,
                "verified": False,
            },
            "weather_forecast": day_forecast,
            "weather_source": forecast.get("source") if day_forecast else None,
            "score": round(score, 1),
            "score_breakdown": {
                "price": round(factor_values["price"] * 100, 1),
                "reviews": round(factor_values["reviews"] * 100, 1),
                "weather": round(factor_values["weather"] * 100, 1) if day_forecast else None,
            },
        })

    ranked_offers.sort(key=lambda offer: offer["score"], reverse=True)
    demo_comparisons = []
    for offer in demo_offers:
        market = MARKETS[offer["market_id"]]
        demo_comparisons.append({
            **offer,
            "market": market["name"],
            "area": market["area"],
            "data_status": market["data_status"],
            "source_name": market["source_name"],
            "source_url": market["source_url"],
            "observed_at": market["observed_at"],
            "total_cost_ngn": round(offer["unit_price_ngn"] * quantity),
            "community_reviews": {"average_rating": None, "review_count": 0, "verified": False},
            "weather_forecast": None,
            "score": None,
            "score_breakdown": None,
        })
    return {
        "product": matching[0]["product"],
        "unit": matching[0]["unit"],
        "requested_quantity": quantity,
        "priority": priority,
        "data_notice": DATA_NOTICE,
        "attribution": ARKETDATA_LICENSE,
        "attribution_url": ARKETDATA_ABOUT_URL,
        "recommendation": ranked_offers[0] if ranked_offers else None,
        "ranked_offers": ranked_offers,
        "demo_comparisons": demo_comparisons,
        "travel_date": travel_date,
        "scoring_weights": weights,
        "recommendation_basis": "Deterministic weighted comparison of sourced same-unit price, unverified community rating, and forecast rain probability. It is a decision aid, not an AI prediction.",
    }
