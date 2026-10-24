"""Customer name confirmation and alias creation through POST /messages (FR-S9, FR-S5; BR-L2 to L8).
Run: cd server && python -m unittest discover -s tests -t ."""

from sqlalchemy import func, select

from app.customers.models import Customer
from app.ledger.models import Entry
from app.shared.Infrastructure.llm.client import LLMError
from tests.support import ApiTestCase, interpretation


class CustomerResolutionTest(ApiTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.trader_id, self.headers = self.onboard()
        saved = self.send(
            self.headers, "Mama Ngozi carry rice 60k credit", "seed",
            interpretation(type="credit_sale", customer="Mama Ngozi", amount_text="60k"),
        ).json()
        self.assertEqual(saved["status"], "saved")

    def payment(self, mention: str, message_id: str, match: dict | Exception | None = None, text: str | None = None):
        """A payment naming `mention`. The model is asked twice: interpretation, then the customer match."""
        self.llm.queue.append(interpretation(type="payment_received", customer=mention, amount_text="thirty k"))
        if match is not None:
            self.llm.queue.append(match)
        return self.send(self.headers, text or f"{mention} don pay thirty k", message_id)

    def customers(self) -> dict[str, list[str]]:
        return {c["canonical_name"]: c["aliases"] for c in self.client.get("/customers", headers=self.headers).json()}

    def count(self, model: type) -> int:
        with self.Session() as db:
            return db.scalar(select(func.count()).select_from(model)) or 0  # pyright: ignore[reportArgumentType]

    def test_unsure_match_asks_then_yes_links_and_saves_the_alias(self) -> None:
        asked = self.payment(
            "the rice woman", "m1", {"customer": "Mama Ngozi", "confidence": 0.7}, "The rice woman don pay thirty k"
        ).json()
        self.assertEqual((asked["status"], asked["message"]), ("clarify", "Do you mean Mama Ngozi?"))
        calls_before_yes = self.llm.calls

        body = self.send(self.headers, "yes", "m2").json()
        self.assertEqual((body["status"], body["entry"]["customer"]), ("saved", "Mama Ngozi"))
        self.assertEqual(self.llm.calls, calls_before_yes)  # yes/no is read in code
        self.assertEqual(self.customers(), {"Mama Ngozi": ["the rice woman"]})

        again = self.payment("the rice woman", "m3").json()
        self.assertEqual((again["status"], again["entry"]["customer"]), ("saved", "Mama Ngozi"))
        self.assertEqual(self.llm.calls, calls_before_yes + 1)  # only the interpretation; no match call
        balances = {c["canonical_name"]: c["balance_ngn"] for c in self.client.get("/customers", headers=self.headers).json()}
        self.assertEqual(balances, {"Mama Ngozi": 0})

    def test_sure_match_links_at_once_and_saves_the_alias(self) -> None:
        body = self.payment("the rice woman", "m1", {"customer": "Mama Ngozi", "confidence": 0.95}).json()
        self.assertEqual((body["status"], body["entry"]["customer"]), ("saved", "Mama Ngozi"))
        self.assertIn("the rice woman", self.customers()["Mama Ngozi"])

    def test_no_creates_a_new_customer_from_the_mention(self) -> None:
        self.payment("Mama Bisi", "m1", {"customer": "Mama Ngozi", "confidence": 0.6})
        body = self.send(self.headers, "no", "m2").json()
        self.assertEqual((body["status"], body["entry"]["customer"]), ("saved", "Mama Bisi"))
        self.assertEqual(set(self.customers()), {"Mama Ngozi", "Mama Bisi"})

    def test_other_reply_repeats_the_question_and_saves_nothing(self) -> None:
        self.payment("the rice woman", "m1", {"customer": "Mama Ngozi", "confidence": 0.6})
        entries = self.count(Entry)
        body = self.send(self.headers, "abeg wait", "m2", interpretation()).json()
        self.assertEqual((body["status"], body["message"]), ("clarify", "Do you mean Mama Ngozi?"))
        self.assertEqual(self.count(Entry), entries)

    def test_offline_guess_is_always_confirmed(self) -> None:
        body = self.payment("Ngozi", "m1", LLMError("down"), "Ngozi don pay 5k").json()  # match call fails
        self.assertEqual((body["status"], body["message"]), ("clarify", "Do you mean Mama Ngozi?"))

    def test_model_answer_outside_the_list_is_ignored(self) -> None:
        body = self.payment("Chidi", "m1", {"customer": "Somebody Else", "confidence": 0.99}).json()
        self.assertEqual((body["status"], body["entry"]["customer"]), ("saved", "Chidi"))

    def test_a_different_complete_entry_replaces_the_pending_one(self) -> None:
        asked = self.send(
            self.headers, "I sell two bags and half", "m1",
            interpretation(type="sale", item="rice", quantity=2.5, unit="bags"),
        ).json()
        self.assertEqual(asked["message"], "How much did you collect for the 2.5 bags?")
        body = self.send(
            self.headers, "I pay transport 2k", "m2", interpretation(type="expense", item="transport", amount_text="2k")
        ).json()
        self.assertEqual((body["status"], body["entry"]["type"], body["entry"]["raw_text"]), ("saved", "expense", "I pay transport 2k"))
        follow_up = self.send(self.headers, "25k", "m3", interpretation(amount_text="25k")).json()
        self.assertEqual(follow_up["status"], "clarify")  # the rice sale was dropped, not completed

    def test_the_same_entry_restated_still_answers_the_question(self) -> None:
        self.send(self.headers, "I sell two bags and half", "m1", interpretation(type="sale", item="rice", quantity=2.5, unit="bags"))
        body = self.send(
            self.headers, "I collect 25k for the rice", "m2", interpretation(type="sale", item="rice", amount_text="25k")
        ).json()
        self.assertEqual((body["status"], body["entry"]["quantity"]), ("saved", 2.5))

    def test_no_to_a_low_confidence_reading_saves_nothing(self) -> None:
        entries = self.count(Entry)
        self.send(self.headers, "rice 10k abi", "m1", interpretation(type="sale", item="rice", amount_text="10k", confidence=0.4))
        body = self.send(self.headers, "no", "m2").json()
        self.assertEqual(body["status"], "fallback")
        self.assertEqual(self.count(Entry), entries)

    def test_expense_question_asks_what_was_paid(self) -> None:
        body = self.send(self.headers, "I buy 5 bags rice", "m1", interpretation(type="expense", item="rice", quantity=5, unit="bag")).json()
        self.assertEqual(body["message"], "How much did you pay for the 5 bags?")

    def test_missing_customer_question(self) -> None:
        body = self.send(self.headers, "credit sale 20k", "m1", interpretation(type="credit_sale", amount_text="20k")).json()
        self.assertEqual(body["message"], "Which customer is this for?")

    def test_new_customer_name_is_its_own_alias(self) -> None:
        with self.Session() as db:
            self.assertEqual(db.scalar(select(func.count(Customer.id))), 1)
        self.assertEqual(self.customers(), {"Mama Ngozi": []})  # the canonical alias is not listed twice


class StockWarningTest(ApiTestCase):
    def test_warning_is_stored_and_listed(self) -> None:
        _, headers = self.onboard()
        self.send(headers, "sold beans 50k", "m1", interpretation(type="sale", item="beans", amount_text="50k"))
        (entry,) = self.client.get("/entries", headers=headers).json()
        self.assertEqual(entry["stock_warning"], "not_in_inventory")
