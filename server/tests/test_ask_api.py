"""POST /ask (FR-S11, FR-S32; BR-Q1, BR-Q2, BR-A7). Run: cd server && python -m unittest discover -s tests -t ."""

from app.shared.Infrastructure.llm.client import LLMError
from tests.support import ApiTestCase, interpretation


class AskApiTest(ApiTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.trader_id, self.headers = self.onboard()
        self.send(self.headers, "Mama Ngozi 60k credit", "e1", interpretation(type="credit_sale", customer="Mama Ngozi", amount_text="60k"))
        self.send(self.headers, "Mama Ngozi pay 30k", "e2", interpretation(type="payment_received", customer="Mama Ngozi", amount_text="30k"))
        self.send(self.headers, "Mr Bayo 50k credit", "e3", interpretation(type="credit_sale", customer="Mr Bayo", amount_text="50k"))
        self.send(self.headers, "sold beans 20k", "e4", interpretation(type="sale", item="beans", amount_text="20k"))

    def ask(self, question: str) -> dict:
        response = self.client.post("/ask", headers=self.headers, json={"question": question})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_who_owes_from_the_database_largest_first_with_no_model_call(self) -> None:
        calls = self.llm.calls
        body = self.ask("Who owes me?")
        self.assertEqual(self.llm.calls, calls)  # keyword routing
        self.assertEqual(body["intent"], "who_owes")
        self.assertEqual([(c["name"], c["balance_ngn"]) for c in body["customers"]], [("Mr Bayo", 50000), ("Mama Ngozi", 30000)])
        self.assertEqual(body["answer"], "Mr Bayo ₦50,000; Mama Ngozi ₦30,000. Total ₦80,000.")

    def test_pidgin_phrasing(self) -> None:
        self.assertEqual(self.ask("who dey owe me")["intent"], "who_owes")
        body = self.ask("how much Ngozi dey owe?")
        self.assertEqual((body["intent"], body["answer"]), ("customer_balance", "Mama Ngozi owes you ₦30,000."))

    def test_today_total_counts_sales_and_credit_sales(self) -> None:
        body = self.ask("How much I sell today?")
        self.assertEqual((body["intent"], body["sales_ngn"]), ("today_total", 130000))

    def test_stock_level(self) -> None:
        self.add_stock(self.trader_id, "rice", "7.5", reorder_level="3", reorder_quantity="10")
        body = self.ask("How many rice remain?")
        self.assertEqual((body["intent"], body["answer"], body["stock"]["quantity_on_hand"]), ("stock_level", "You have 7.5 bags of rice left.", 7.5))

    def test_restock_answer_matches_get_suggestions(self) -> None:
        self.add_stock(self.trader_id, "rice", "1", reorder_level="3", reorder_quantity="10")
        self.llm.queue.append(LLMError("down"))
        body = self.ask("Where I fit buy rice?")
        self.llm.queue.append(LLMError("down"))
        direct = self.client.get("/suggestions?item=rice&quantity=10", headers=self.headers).json()
        self.assertEqual(body["intent"], "restock_suggestion")
        self.assertEqual(body["suggestions"], direct)
        self.assertTrue(body["answer"].startswith("Demo data. 1. "))

    def test_restock_without_a_quantity_asks_how_many(self) -> None:
        body = self.ask("where I fit buy garri")
        self.assertEqual(body["intent"], "restock_suggestion")
        self.assertTrue(body["answer"].startswith("How many garri do you need?"))

    def test_model_routes_unmatched_questions_but_cannot_change_figures(self) -> None:
        self.llm.queue.append({"intent": "who_owes", "answer": "Everybody owes you ₦1,000,000", "total": 1000000})
        body = self.ask("abeg check my debtors list for me")
        self.assertEqual(body["answer"], "Mr Bayo ₦50,000; Mama Ngozi ₦30,000. Total ₦80,000.")

    def test_model_customer_outside_the_list_is_dropped(self) -> None:
        self.llm.queue.append({"intent": "customer_balance", "customer": "Somebody Else"})
        self.assertEqual(self.ask("that woman, wetin be her account?")["intent"], "unknown")

    def test_unknown_question_gets_a_fallback(self) -> None:
        self.llm.queue.append({"intent": "unknown"})
        body = self.ask("what is the weather?")
        self.assertEqual(body["intent"], "unknown")
        self.assertTrue(body["answer"].startswith("I can tell you"))

    def test_model_down_gives_the_fallback(self) -> None:
        self.llm.queue.append(LLMError("down"))
        self.assertEqual(self.ask("tell me something about my business")["intent"], "unknown")

    def test_no_token_is_401(self) -> None:
        self.assertEqual(self.client.post("/ask", json={"question": "who owes me"}).status_code, 401)
