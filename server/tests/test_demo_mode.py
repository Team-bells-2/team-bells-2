"""DEMO_MODE (NFR-4; BR-A3, BR-A4, BR-L1) and the demo controls (FR-C10; BR-D1).
Run: cd server && python -m unittest discover -s tests -t ."""

from datetime import datetime, timedelta
from unittest import mock

from sqlalchemy import func, select

from app.ai.dependencies import get_ai_orchestrator
from app.ai.orchestrator import AIOrchestrator
from app.ai.services import demo_interpret
from app.onboarding.models import Trader
from app.shared.env import settings
from app.shared.periods import LAGOS
from tests.support import ApiTestCase

CUSTOMERS = [{"name": "Mama Ngozi", "aliases": ["Ngozi", "the rice woman"]}, {"name": "Mr Bayo", "aliases": ["Bayo"]}]


class DemoInterpretTest(ApiTestCase):
    def read(self, text: str, **context: object) -> dict:
        return demo_interpret(text, {"customers": CUSTOMERS, "items": ["rice", "garri"], **context})

    def test_credit_sale_with_due_phrase(self) -> None:
        r = self.read("I give Mama Ngozi two bags rice on credit for sixty k, she go pay Friday")
        self.assertEqual(
            (r["type"], r["customer"], r["item"], r["quantity"], r["unit"], r["amount_text"], r["due_text"]),
            ("credit_sale", "Mama Ngozi", "rice", 2, "bag", "sixty k", "friday"),
        )

    def test_nickname_is_the_customer_not_the_item(self) -> None:
        r = self.read("The rice woman don pay thirty k")
        self.assertEqual((r["type"], r["customer"], r["item"], r["amount_text"]), ("payment_received", "Mama Ngozi", None, "thirty k"))

    def test_half_quantity_without_amount_is_incomplete(self) -> None:
        r = self.read("I sell two bags and half")
        self.assertEqual((r["type"], r["quantity"], r["amount_text"]), ("sale", 2.5, None))
        self.assertLess(r["confidence"], settings.CONFIDENCE_THRESHOLD)

    def test_expense(self) -> None:
        r = self.read("I pay transport 2k")
        self.assertEqual((r["type"], r["amount_text"]), ("expense", "2k"))

    def test_pending_answer(self) -> None:
        pending = {"fields": {"type": "sale", "quantity": "2.5", "unit": "bag"}, "question": "How much?"}
        self.assertEqual(self.read("25k", pending=pending)["amount_text"], "25k")

    def test_corrections(self) -> None:
        last = {"type": "sale", "item": "rice", "quantity": "2.5", "unit": "bag", "amount_ngn": "25000"}
        r = self.read("No, I mean four bags", last_entry=last)
        self.assertEqual((r["intent"], r["quantity"], r["unit"]), ("correction", 4, "bag"))
        self.assertEqual(self.read("Sorry na 55k, not 60k", last_entry=last)["amount_text"], "55k")

    def test_off_topic(self) -> None:
        self.assertEqual(self.read("how far, wetin dey happen")["intent"], "unknown")


class DemoControlsTest(ApiTestCase):
    def test_disabled_by_default(self) -> None:
        for path in ("/demo/reset", "/demo/seed"):
            with self.subTest(path=path):
                response = self.client.post(path)
                self.assertEqual((response.status_code, response.json()["error"]["code"]), (403, "demo_controls_disabled"))

    def test_seed_then_reset(self) -> None:
        with mock.patch.object(settings, "DEMO_CONTROLS_ENABLED", True):
            first = self.client.post("/demo/seed").json()
            second = self.client.post("/demo/seed").json()  # safe to run twice
            headers = {"Authorization": f"Bearer {second['token']}"}
            self.assertEqual(first["trader_id"], second["trader_id"])
            inventory = {i["name"]: i["quantity_on_hand"] for i in self.client.get("/inventory", headers=headers).json()}
            self.assertEqual(inventory, {"beans": 6, "garri": 2, "oil": 5, "rice": 10})
            customers = {c["canonical_name"]: c["aliases"] for c in self.client.get("/customers", headers=headers).json()}
            self.assertEqual(customers["Mama Ngozi"], ["Ngozi", "the rice woman"])
            self.assertEqual(self.client.post("/auth/login", json={"phone": first["phone"], "pin": first["pin"]}).status_code, 200)

            started = datetime.now()
            reset = self.client.post("/demo/reset").json()
            self.assertLess(datetime.now() - started, timedelta(seconds=10))
        self.assertEqual(reset["status"], "reset")
        with self.Session() as db:
            self.assertEqual(db.scalar(select(func.count(Trader.id))), 0)
        self.assertEqual(self.client.get("/profile", headers=headers).status_code, 401)


class GoldenPathOfflineTest(ApiTestCase):
    """The 8-step demo (PRD section 3) with DEMO_MODE on: no provider call at all (NFR-4)."""

    def setUp(self) -> None:
        super().setUp()
        from app.main import app

        app.dependency_overrides[get_ai_orchestrator] = lambda: AIOrchestrator(self.llm, demo_mode=True)  # pyright: ignore[reportArgumentType]

    def message(self, headers: dict[str, str], text: str, message_id: str) -> dict:
        response = self.client.post("/messages", headers=headers, json={"text": text, "client_message_id": message_id})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_golden_path(self) -> None:
        # 1. A new trader onboards and picks a sector; the demo trader is seeded for the rest.
        onboard = self.client.post("/onboarding", json={
            "name": "Ada Obi", "phone": "08031234567", "business_name": "Ada Foods", "sector": "foodstuff",
            "location_name": "Mile 12", "items": [{"name": "rice", "unit": "bag", "opening_quantity": 5}],
        })
        self.assertEqual(onboard.status_code, 201)
        with mock.patch.object(settings, "DEMO_CONTROLS_ENABLED", True):
            demo = self.client.post("/demo/seed").json()
        h = {"Authorization": f"Bearer {demo['token']}"}

        # 2. A credit sale by voice.
        self.stt.text = "I give Mama Ngozi two bags rice on credit for sixty k, she go pay Friday"
        voice = self.client.post("/messages", headers=h, files={"audio": ("v.m4a", b"audio", "audio/m4a")},
                                 data={"client_message_id": "g2"}).json()
        today = datetime.now(LAGOS).date()
        friday = today + timedelta(days=(4 - today.weekday()) % 7 or 7)
        self.assertEqual((voice["status"], voice["entry"]["amount_ngn"], voice["entry"]["customer"], voice["entry"]["due_date"]),
                         ("saved", 60000, "Mama Ngozi", friday.isoformat()))

        # 3. An ambiguous sale is clarified, then 4. corrected.
        self.assertEqual(self.message(h, "I sell two bags and half", "g3a")["message"], "How much did you collect for the 2.5 bags?")
        saved = self.message(h, "25k", "g3b")
        self.assertEqual((saved["status"], saved["entry"]["amount_ngn"]), ("saved", 25000))
        corrected = self.message(h, "No, I mean four bags", "g4")
        self.assertEqual((corrected["status"], corrected["entry"]["id"], corrected["entry"]["quantity"]), ("corrected", saved["entry"]["id"], 4))

        # 5. A payment against a nickname.
        paid = self.message(h, "The rice woman don pay thirty k", "g5")
        self.assertEqual((paid["entry"]["type"], paid["entry"]["customer"], paid["entry"]["amount_ngn"]), ("payment_received", "Mama Ngozi", 30000))

        # 6. Who owes?
        ask = self.client.post("/ask", headers=h, json={"question": "Who owes me?"}).json()
        self.assertEqual(ask["answer"], "Mama Ngozi ₦30,000. Total ₦30,000.")

        # 7. Home: profit and loss, items logged, stock and a restock suggestion.
        home = self.client.get("/home?period=7d", headers=h).json()
        self.assertEqual((home["revenue_ngn"], home["total_owed_ngn"], home["items_logged"]), (85000, 30000, 3))
        (garri,) = home["low_stock_items"]
        self.assertEqual(garri["name"], "garri")
        self.assertTrue(garri["top_suggestion"]["reason"].startswith("Recommended: "))
        rice = next(i for i in self.client.get("/inventory", headers=h).json() if i["name"] == "rice")
        self.assertEqual(rice["quantity_on_hand"], 8)

        # 8. A lender agent is approved and reads its summary.
        created = self.client.post("/access-requests", json={
            "trader_phone": demo["phone"], "agent_name": "QuickLoan agent", "purpose": "Credit readiness",
            "data_scopes": ["sales_total", "total_owed"],
        }).json()
        self.client.post(f"/access-requests/{created['request_id']}/approve", headers=h, json={"approve": True})
        token = self.client.get(f"/access-requests/{created['request_id']}/status",
                                headers={"X-Claim-Secret": created["claim_secret"]}).json()["access_token"]
        summary = self.client.get("/agent/summary", headers={"Authorization": f"Bearer {token}"}).json()
        self.assertEqual((summary["sales_total_ngn"], summary["total_owed_ngn"]), (85000, 30000))

        self.assertEqual(self.llm.calls, 0)  # no provider was called at any step
