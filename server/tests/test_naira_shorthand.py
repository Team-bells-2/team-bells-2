"""FR-S4: naira shorthand and word numbers are normalised in code. Run: cd server && python -m unittest discover -s tests -t ."""

import unittest
from decimal import Decimal

from app.ledger.services import parse_naira_amount


class NairaShorthandTest(unittest.TestCase):
    CASES: list[tuple[str, str]] = [
        ("ten k", "10000"),
        ("10k", "10000"),
        ("10K", "10000"),
        ("2.5k", "2500"),
        ("sixty k", "60000"),
        ("thirty k", "30000"),
        ("twenty-five k", "25000"),
        ("₦60,000", "60000"),
        ("N60,000", "60000"),
        ("60000", "60000"),
        ("60,000 naira", "60000"),
        ("sixty thousand", "60000"),
        ("15 thousand", "15000"),
        ("one hundred and fifty thousand", "150000"),
        ("five hundred", "500"),
        ("fifty naira", "50"),
        ("1.2m", "1200000"),
        ("two million", "2000000"),
        ("two and half k", "2500"),
        ("a thousand", "1000"),
        ("two and a half k", "2500"),
        ("₦ 2.5k", "2500"),
        ("one thousand five hundred", "1500"),
    ]

    def test_variants(self) -> None:
        for phrase, expected in self.CASES:
            with self.subTest(phrase=phrase):
                self.assertEqual(parse_naira_amount(phrase), Decimal(expected))

    def test_unrecognisable_returns_none(self) -> None:
        for phrase in ["", "plenty money", "k", "thousand", "abc 10k"]:
            with self.subTest(phrase=phrase):
                self.assertIsNone(parse_naira_amount(phrase))


if __name__ == "__main__":
    unittest.main()
