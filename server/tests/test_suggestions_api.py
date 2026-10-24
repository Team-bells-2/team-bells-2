"""GET /suggestions on seeded demo data, and the seed itself (FR-S29 to S31).
Run: cd server && python -m unittest discover -s tests -t ."""

from app.shared.Infrastructure.llm.client import LLMError
from tests.support import ApiTestCase, demo_orchestrator


class SuggestionsApiTest(ApiTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.trader_id, self.headers = self.onboard()

    def get(self, query: str):
        return self.client.get(f"/suggestions?{query}", headers=self.headers)

    def test_three_suppliers_labelled_demo_data_with_template_reason_when_model_fails(self) -> None:
        self.llm.queue.append(LLMError("down"))
        body = self.get("item=rice&quantity=10").json()
        self.assertEqual((body["data_label"], body["quantity_needed"], len(body["suggestions"])), ("Demo data", 10, 3))
        self.assertTrue(all(s["reason"] for s in body["suggestions"]))

    def test_model_wording_never_changes_order_or_figures(self) -> None:
        self.llm.queue.append(LLMError("down"))
        template = self.get("item=rice&quantity=10").json()["suggestions"]
        self.llm.queue.append({"reasons": ["A", "B", "C"]})
        worded = self.get("item=rice&quantity=10").json()["suggestions"]
        self.assertEqual([s["reason"] for s in worded], ["A", "B", "C"])
        strip = lambda rows: [{k: v for k, v in row.items() if k != "reason"} for row in rows]  # noqa: E731
        self.assertEqual(strip(worded), strip(template))

    def test_suppliers_that_can_fill_rank_first(self) -> None:
        self.llm.queue.append(LLMError("down"))
        rows = self.get("item=rice&quantity=50").json()["suggestions"]
        fills = [s["can_fill"] for s in rows]
        self.assertEqual(fills, sorted(fills, reverse=True))

    def test_quantity_defaults_to_reorder_quantity(self) -> None:
        self.add_stock(self.trader_id, "rice", "1", reorder_level="2", reorder_quantity="10")
        self.llm.queue.append(LLMError("down"))
        self.assertEqual(self.get("item=rice").json()["quantity_needed"], 10)

    def test_no_quantity_and_no_reorder_quantity_is_422(self) -> None:
        response = self.get("item=garri")
        self.assertEqual((response.status_code, response.json()["error"]["code"]), (422, "quantity_required"))

    def test_prototype_routes_are_not_served(self) -> None:
        for path in ("/markets", "/markets/reviews", "/transcribe", "/dashboard"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)


class SeedTest(ApiTestCase):
    def test_seed_is_idempotent(self) -> None:
        with self.Session() as db:  # setUp already seeded once
            summary = demo_orchestrator(db).seed_reference_data()
        self.assertEqual(summary.model_dump(), {"locations_added": 0, "suppliers_added": 0, "offers_added": 0, "reviews_added": 0})
