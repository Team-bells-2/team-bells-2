"""Item and unit matching: case, spaces, plural endings and the model fallback (FR-S25, FR-S30; decision D6).
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


class ItemModelMatchTest(ApiTestCase):
    """FR-S25: name first, then the model against the trader's inventory, like customers (FR-S9)."""

    def setUp(self) -> None:
        super().setUp()
        self.trader_id, self.headers = self.onboard()
        self.oil = self.add_stock(self.trader_id, "oil", "10")

    def palm_oil_sale(self, match: dict | None, message_id: str = "m1") -> dict:
        self.llm.queue.append(interpretation(type="sale", item="palm oil", quantity=2, unit="bag", amount_text="20k"))
        if match is not None:
            self.llm.queue.append(match)
        return self.client.post(
            "/messages", headers=self.headers, json={"text": "sold 2 bags palm oil 20k", "client_message_id": message_id}
        ).json()

    def test_sure_match_links_the_inventory_item(self) -> None:
        body = self.palm_oil_sale({"item": "oil", "confidence": 0.95})
        self.assertEqual((body["status"], body["entry"]["item"], body["flags"]), ("saved", "oil", []))
        self.assertEqual(self.on_hand(self.oil), Decimal(8))

    def test_unsure_match_asks_then_yes_links(self) -> None:
        asked = self.palm_oil_sale({"item": "oil", "confidence": 0.6})
        self.assertEqual((asked["status"], asked["message"]), ("clarify", "Do you mean oil?"))
        calls = self.llm.calls
        body = self.client.post("/messages", headers=self.headers, json={"text": "yes", "client_message_id": "m2"}).json()
        self.assertEqual((body["status"], body["entry"]["item"]), ("saved", "oil"))
        self.assertEqual(self.llm.calls, calls)  # yes/no is read in code
        self.assertEqual(self.on_hand(self.oil), Decimal(8))

    def test_unsure_match_then_no_keeps_the_name_as_not_in_inventory(self) -> None:
        self.palm_oil_sale({"item": "oil", "confidence": 0.6})
        body = self.client.post("/messages", headers=self.headers, json={"text": "no", "client_message_id": "m2"}).json()
        self.assertEqual((body["status"], body["entry"]["item"], body["flags"]), ("saved", "palm oil", ["not_in_inventory"]))
        self.assertEqual(self.on_hand(self.oil), Decimal(10))

    def test_model_answer_outside_the_inventory_is_ignored(self) -> None:
        body = self.palm_oil_sale({"item": "yam", "confidence": 0.99})
        self.assertEqual((body["entry"]["item"], body["flags"]), ("palm oil", ["not_in_inventory"]))

    def test_low_confidence_saves_as_not_in_inventory_without_asking(self) -> None:
        body = self.palm_oil_sale({"item": "oil", "confidence": 0.2})
        self.assertEqual((body["status"], body["flags"]), ("saved", ["not_in_inventory"]))

    def test_item_then_customer_questions_come_one_at_a_time(self) -> None:
        self.send(self.headers, "Mama Ngozi carry 1 bag oil 5k credit", "seed",
                  interpretation(type="credit_sale", item="oil", quantity=1, unit="bag", customer="Mama Ngozi", amount_text="5k"))
        self.llm.queue += [
            interpretation(type="credit_sale", item="palm oil", quantity=1, unit="bag", customer="the rice woman", amount_text="5k"),
            {"item": "oil", "confidence": 0.6},
        ]
        asked = self.client.post("/messages", headers=self.headers, json={"text": "rice woman carry palm oil 5k credit", "client_message_id": "m1"}).json()
        self.assertEqual(asked["message"], "Do you mean oil?")
        self.llm.queue.append({"customer": "Mama Ngozi", "confidence": 0.6})
        second = self.client.post("/messages", headers=self.headers, json={"text": "yes", "client_message_id": "m2"}).json()
        self.assertEqual(second["message"], "Do you mean Mama Ngozi?")
        done = self.client.post("/messages", headers=self.headers, json={"text": "yes", "client_message_id": "m3"}).json()
        self.assertEqual((done["status"], done["entry"]["item"], done["entry"]["customer"]), ("saved", "oil", "Mama Ngozi"))

    def test_correction_links_only_when_sure(self) -> None:
        self.send(self.headers, "sold 2 bag beans 20k", "m1", interpretation(type="sale", item="beans", quantity=2, unit="bag", amount_text="20k"))
        self.llm.queue.append({"intent": "correction", "confidence": 0.9, "item": "palm oil"})
        self.llm.queue.append({"item": "oil", "confidence": 0.95})
        body = self.client.post("/messages", headers=self.headers, json={"text": "no be beans, na palm oil", "client_message_id": "m2"}).json()
        self.assertEqual((body["status"], body["entry"]["item"]), ("corrected", "oil"))
        self.assertEqual(self.on_hand(self.oil), Decimal(8))

    def test_demo_mode_never_calls_the_model_for_items(self) -> None:
        from app.ai.dependencies import get_ai_orchestrator
        from app.ai.orchestrator import AIOrchestrator
        from app.main import app

        app.dependency_overrides[get_ai_orchestrator] = lambda: AIOrchestrator(self.llm, demo_mode=True)  # pyright: ignore[reportArgumentType]
        body = self.client.post("/messages", headers=self.headers, json={"text": "I sell 2 bags palm oil 20k", "client_message_id": "m1"}).json()
        self.assertEqual((body["status"], self.llm.calls), ("saved", 0))
