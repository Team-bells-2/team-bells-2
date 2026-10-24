"""FR-S30: deterministic ranking, monotonic in each factor, can-fill suppliers first.
Run: cd server && python -m unittest discover -s tests -t ."""

import unittest
from dataclasses import replace
from decimal import Decimal

from app.suggestions.services import Candidate, RankingWeights, rank_candidates

WEIGHTS = RankingWeights(
    distance=0.25,
    rating=0.2,
    quality=0.15,
    cost=0.25,
    quantity=0.15,
    distance_half_km=10,
    quality_scores={"A": 1.0, "B": 0.7, "C": 0.4},
)
ORIGIN = (6.6050, 3.3980)
NEEDED = Decimal(10)


def candidate(supplier_id: int, **overrides: object) -> Candidate:
    base = Candidate(
        supplier_id=supplier_id,
        supplier_name=f"Supplier {supplier_id}",
        area="Lagos",
        latitude=6.60 - supplier_id * 0.01,
        longitude=3.39,
        unit="bag",
        unit_price_ngn=Decimal(75000),
        quantity_available=Decimal(50),
        quality_grade="B",
        average_rating=4.0,
        review_count=3,
    )
    return replace(base, **overrides)  # pyright: ignore[reportArgumentType]


def order(candidates: list[Candidate]) -> list[int]:
    return [s.candidate.supplier_id for s in rank_candidates(candidates, ORIGIN, NEEDED, WEIGHTS)]


class RankingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.pool = [
            candidate(1, unit_price_ngn=Decimal(80000), quality_grade="A"),
            candidate(2, unit_price_ngn=Decimal(72000), quality_grade="C", average_rating=3.0),
            candidate(3, average_rating=4.7),
            candidate(4, quantity_available=Decimal(12), quality_grade="A"),
            candidate(5, unit_price_ngn=Decimal(70000), latitude=6.40),
        ]

    def test_same_input_same_order(self) -> None:
        first = order(self.pool)
        for _ in range(5):
            self.assertEqual(order(list(reversed(self.pool))), first)

    def test_cannot_fill_ranks_below_can_fill(self) -> None:
        pool = [candidate(1, quantity_available=Decimal(3), quality_grade="A", average_rating=5.0), candidate(2)]
        self.assertEqual(order(pool), [2, 1])

    def test_improving_one_factor_never_lowers_rank(self) -> None:
        improvements = {
            "cheaper": {"unit_price_ngn": Decimal(60000)},
            "closer": {"latitude": ORIGIN[0], "longitude": ORIGIN[1]},
            "better rating": {"average_rating": 5.0},
            "better quality": {"quality_grade": "A"},
            "more stock": {"quantity_available": Decimal(500)},
        }
        for target in self.pool:
            before = order(self.pool).index(target.supplier_id)
            for label, change in improvements.items():
                with self.subTest(supplier=target.supplier_id, improvement=label):
                    improved = [replace(c, **change) if c is target else c for c in self.pool]  # pyright: ignore[reportArgumentType]
                    self.assertLessEqual(order(improved).index(target.supplier_id), before)

    def test_figures_are_not_changed(self) -> None:
        ranked = rank_candidates(self.pool, ORIGIN, NEEDED, WEIGHTS)
        for scored in ranked:
            source = next(c for c in self.pool if c.supplier_id == scored.candidate.supplier_id)
            self.assertEqual(scored.candidate, source)


if __name__ == "__main__":
    unittest.main()
