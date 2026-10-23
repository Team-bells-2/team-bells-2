from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx


OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_ATTRIBUTION = "Weather data by Open-Meteo, CC BY 4.0"
WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    80: "Rain showers",
    81: "Moderate rain showers",
    82: "Heavy rain showers",
    95: "Thunderstorm",
    96: "Thunderstorm with hail",
    99: "Heavy thunderstorm with hail",
}

MARKET_COORDINATES: dict[str, tuple[float, float]] = {
    "ajah": (6.4698, 3.5852),
    "century": (6.5244, 3.3792),
    "mile-12": (6.6059, 3.3977),
    "agege": (6.6156, 3.3333),
    "balogun": (6.4549, 3.3915),
}

_cache: dict[str, Any] = {"expires_at": datetime.min.replace(tzinfo=UTC), "forecasts": {}}


async def fetch_lagos_market_forecasts(
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Fetch a short daily forecast for configured Lagos market coordinates."""
    now = datetime.now(UTC)
    if now < _cache["expires_at"]:
        return _cache["forecasts"]

    owns_client = client is None
    request_client = client or httpx.AsyncClient(timeout=8.0)
    latitudes = ",".join(str(coordinates[0]) for coordinates in MARKET_COORDINATES.values())
    longitudes = ",".join(str(coordinates[1]) for coordinates in MARKET_COORDINATES.values())
    try:
        response = await request_client.get(
            OPEN_METEO_URL,
            params={
                "latitude": latitudes,
                "longitude": longitudes,
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum",
                "forecast_days": 7,
                "timezone": "Africa/Lagos",
            },
        )
        response.raise_for_status()
        payload = response.json()
    finally:
        if owns_client:
            await request_client.aclose()

    locations = payload if isinstance(payload, list) else [payload]
    forecasts = {}
    for market_id, location in zip(MARKET_COORDINATES, locations):
        daily = location.get("daily") or {}
        days = []
        for index, day in enumerate(daily.get("time", [])):
            code_values = daily.get("weather_code", [])
            probability_values = daily.get("precipitation_probability_max", [])
            precipitation_values = daily.get("precipitation_sum", [])
            max_values = daily.get("temperature_2m_max", [])
            min_values = daily.get("temperature_2m_min", [])
            code = code_values[index] if index < len(code_values) else None
            probability = probability_values[index] if index < len(probability_values) else None
            days.append({
                "date": day,
                "weather_code": code,
                "condition": WEATHER_CODES.get(code, "Weather conditions unavailable") if code is not None else None,
                "temperature_max_c": max_values[index] if index < len(max_values) else None,
                "temperature_min_c": min_values[index] if index < len(min_values) else None,
                "precipitation_probability_max_percent": probability,
                "precipitation_sum_mm": precipitation_values[index] if index < len(precipitation_values) else None,
                "rain_score": max(0.0, min(1.0, 1 - probability / 100)) if probability is not None else None,
            })
        forecasts[market_id] = {
            "market_id": market_id,
            "latitude": location.get("latitude"),
            "longitude": location.get("longitude"),
            "timezone": location.get("timezone", "Africa/Lagos"),
            "forecast_days": days,
        }

    _cache["forecasts"] = forecasts
    _cache["expires_at"] = now + timedelta(minutes=15)
    return forecasts
