"""Ranking weights for restock suggestions (FR-S30). The only place these numbers live."""

WEIGHTS = {
    "distance": 0.25,
    "rating": 0.20,
    "quality": 0.20,
    "cost": 0.25,
    "quantity": 0.10,
}

QUALITY_SCORES = {"A": 1.0, "B": 0.6, "C": 0.2}

# Distance at which the distance score halves.
DISTANCE_HALF_KM = 5.0

MAX_SUGGESTIONS = 3
