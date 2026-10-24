"""Home P&L, customer balances, entries and inventory (FR-S10, S23, S24, S27, S28).
Uses period=7d so a test run near Lagos midnight cannot flip "today".
Run: cd server && python -m unittest discover -s tests -t ."""

from datetime import datetime

from app.shared.periods import LAGOS, period_start
from app.shared.Infrastructure.llm.client import LLMError
from tests.support import ApiTestCase, interpretation


class HomeAndCustomersTest(ApiTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.trader_id, self.headers = self.onboard()

    def record_prd_example(self) -> None:
        """FR-S27 acceptance: 50k sale, 60k credit sale, 30k payment from that customer, 40k expense."""
        self.send(self.headers, "sold beans 50k", "e1", interpretation(type="sale", item="beans", amount_text="50k"))
        self.send(self.headers, "Mama Ngozi 60k credit", "e2", interpretation(type="credit_sale", customer="Mama Ngozi", amount_text="60k"))
        self.send(self.headers, "Mama Ngozi pay 30k", "e3", interpretation(type="payment_received", customer="Mama Ngozi", amount_text="30k"))
        self.send(self.headers, "transport 40k", "e4", interpretation(type="expense", item="transport", amount_text="40k"))

    def test_home_matches_prd_worked_example(self) -> None:
        self.record_prd_example()
        home = self.client.get("/home?period=7d", headers=self.headers).json()
        figures = (home["revenue_ngn"], home["expenses_ngn"], home["profit_ngn"], home["total_owed_ngn"], home["items_logged"])
        self.assertEqual(figures, (110000, 40000, 70000, 30000, 4))

    def test_loss_shows_as_negative_profit(self) -> None:
        self.send(self.headers, "transport 40k", "e1", interpretation(type="expense", item="transport", amount_text="40k"))
        self.assertEqual(self.client.get("/home?period=7d", headers=self.headers).json()["profit_ngn"], -40000)

    def test_customer_balance_is_derived_from_entries(self) -> None:
        self.record_prd_example()
        customers = self.client.get("/customers", headers=self.headers).json()
        self.assertEqual([(c["canonical_name"], c["balance_ngn"]) for c in customers], [("Mama Ngozi", 30000)])

    def test_overpayment_shows_negative_balance_and_does_not_reduce_total_owed(self) -> None:
        self.send(self.headers, "Bisi 10k credit", "e1", interpretation(type="credit_sale", customer="Bisi", amount_text="10k"))
        self.send(self.headers, "Bisi pay 15k", "e2", interpretation(type="payment_received", customer="Bisi", amount_text="15k"))
        self.send(self.headers, "Chidi 20k credit", "e3", interpretation(type="credit_sale", customer="Chidi", amount_text="20k"))
        balances = {c["canonical_name"]: c["balance_ngn"] for c in self.client.get("/customers", headers=self.headers).json()}
        self.assertEqual(balances, {"Bisi": -5000, "Chidi": 20000})
        self.assertEqual(self.client.get("/home?period=7d", headers=self.headers).json()["total_owed_ngn"], 20000)

    def test_entries_newest_first_and_filtered_by_type(self) -> None:
        self.record_prd_example()
        entries = self.client.get("/entries", headers=self.headers).json()
        self.assertEqual([e["type"] for e in entries], ["expense", "payment_received", "credit_sale", "sale"])
        expenses = self.client.get("/entries?type=expense", headers=self.headers).json()
        self.assertEqual([e["item"] for e in expenses], ["transport"])

    def test_invalid_period_is_422(self) -> None:
        self.assertEqual(self.client.get("/entries?period=1y", headers=self.headers).status_code, 422)

    def test_one_trader_never_sees_another_traders_data(self) -> None:
        self.record_prd_example()
        _, other = self.onboard(phone="08030000009")
        self.assertEqual(self.client.get("/entries", headers=other).json(), [])
        self.assertEqual(self.client.get("/customers", headers=other).json(), [])
        self.assertEqual(self.client.get("/home?period=7d", headers=other).json()["revenue_ngn"], 0)


class InventoryTest(ApiTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.trader_id, self.headers = self.onboard()

    def test_quantity_is_derived_from_movements_and_low_stock_flagged(self) -> None:
        self.add_stock(self.trader_id, "Rice", "10", reorder_level="8")
        self.send(self.headers, "sold 2.5 bags rice", "e1", interpretation(type="sale", item="rice", quantity=2.5, unit="bag", amount_text="25k"))
        (item,) = self.client.get("/inventory", headers=self.headers).json()
        self.assertEqual((item["name"], item["quantity_on_hand"], item["low_stock"]), ("Rice", 7.5, True))
        home = self.client.get("/home?period=7d", headers=self.headers).json()
        self.assertEqual([i["name"] for i in home["low_stock_items"]], ["Rice"])


class PeriodTest(ApiTestCase):
    def test_periods_start_at_lagos_midnight(self) -> None:
        now = datetime(2026, 10, 24, 0, 30, tzinfo=LAGOS)  # 23:30 UTC on the 23rd
        self.assertEqual(period_start("today", now), datetime(2026, 10, 24, tzinfo=LAGOS))
        self.assertEqual(period_start("7d", now), datetime(2026, 10, 18, tzinfo=LAGOS))
        self.assertEqual(period_start("30d", now), datetime(2026, 9, 25, tzinfo=LAGOS))


class HomeRestockCardTest(ApiTestCase):
    """FR-S32 / FR-C17 / FR-C13; BR-H1, BR-H2, BR-S2."""

    def setUp(self) -> None:
        super().setUp()
        self.trader_id, self.headers = self.onboard()

    def test_low_stock_item_carries_the_same_top_supplier_as_suggestions_with_no_model_call(self) -> None:
        self.add_stock(self.trader_id, "rice", "2", reorder_level="3", reorder_quantity="10")
        calls = self.llm.calls
        (card,) = self.client.get("/home?period=7d", headers=self.headers).json()["low_stock_items"]
        self.assertEqual(self.llm.calls, calls)
        self.llm.queue.append(LLMError("down"))
        top = self.client.get("/suggestions?item=rice&quantity=10", headers=self.headers).json()["suggestions"][0]
        self.assertEqual(card["top_suggestion"], top)
        self.assertTrue(card["top_suggestion"]["reason"].startswith("Recommended: "))

    def test_no_card_suggestion_without_a_reorder_quantity(self) -> None:
        self.add_stock(self.trader_id, "rice", "0", reorder_level="3")
        (card,) = self.client.get("/home?period=7d", headers=self.headers).json()["low_stock_items"]
        self.assertIsNone(card["top_suggestion"])

    def test_recent_entries_newest_first(self) -> None:
        for index in range(12):
            self.send(self.headers, f"sold {index}", f"e{index}", interpretation(type="sale", amount_text=f"{index + 1}k"))
        recent = self.client.get("/home?period=7d", headers=self.headers).json()["recent_entries"]
        self.assertEqual([e["amount_ngn"] for e in recent], [float(n * 1000) for n in range(12, 2, -1)])
