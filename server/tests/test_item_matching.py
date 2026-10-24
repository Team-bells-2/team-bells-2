"""Item and unit matching: case, spaces and plural endings (FR-S25, FR-S30; server/TODO.txt item 1).
Run: cd server && python -m unittest discover -s tests -t ."""

import unittest
from decimal import Decimal

import tests.support  # noqa: F401  (test settings first)
from app.shared.matching import match_key
from tests.support import ApiTestCase, interpretation


class MatchKeyTest(unittest.TestCase):
    def test_equal_keys(self) -> None:
        for a, b in [("Rice", "rice"), ("rices", "rice"), ("bags", "bag"), ("Bags", "BAG"), ("tomatoes", "tomato"),
                     ("palm  oils", "palm oil"), ("beans", "BEANS"), ("kg", "kg")]:
            with self.subTest(a=a, b=b):
                self.assertEqual(match_key(a), match_key(b))

    def test_different_keys(self) -> None:
        for a, b in [("rice", "beans"), ("bag", "cup"), ("palm oil", "oil"), ("glass", "glas")]:
            with self.subTest(a=a, b=b):
                self.assertNotEqual(match_key(a), match_key(b))


class ItemMatchingApiTest(ApiTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.trader_id, self.headers = self.onboard()
        self.rice = self.add_stock(self.trader_id, "Rice", "10")

    def sale(self, item: str, unit: str, message_id: str) -> dict:
        return self.send(
            self.headers, f"sold 2 {unit} {item} 20k", message_id,
            interpretation(type="sale", item=item, quantity=2, unit=unit, amount_text="20k"),
        ).json()

    def test_plural_item_and_unit_move_stock(self) -> None:
        body = self.sale("rices", "bags", "m1")
        self.assertEqual((body["flags"], self.on_hand(self.rice)), ([], Decimal(8)))

    def test_a_different_unit_is_flagged_and_moves_no_stock(self) -> None:
        body = self.sale("rice", "cups", "m1")
        self.assertEqual((body["status"], body["flags"]), ("saved", ["check_stock"]))
        self.assertEqual(self.on_hand(self.rice), Decimal(10))

    def test_adding_a_plural_of_an_existing_item_is_a_duplicate(self) -> None:
        response = self.client.post("/inventory", headers=self.headers, json={"name": "rices", "unit": "bag"})
        self.assertEqual(response.status_code, 409)

    def test_suggestions_match_a_plural_item(self) -> None:
        self.llm.queue.append({"reasons": ["a", "b", "c"]})
        body = self.client.get("/suggestions?item=Rices&quantity=1", headers=self.headers).json()
        self.assertEqual(len(body["suggestions"]), 3)
