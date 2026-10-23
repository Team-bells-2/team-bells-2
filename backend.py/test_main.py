import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from fastapi.testclient import TestClient

from main import create_app


class BackendApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "test.sqlite3"
        self.client = TestClient(create_app(database_path))

    def tearDown(self) -> None:
        self.client.close()
        self.temp_dir.cleanup()

    def test_entries_persist_and_filter_by_type(self) -> None:
        response = self.client.post(
            "/entries",
            json={
                "type": "credit_sale",
                "item": "rice",
                "quantity": 2,
                "unit": "bags",
                "amount_ngn": 60000,
                "customer": "Mama Ngozi",
                "raw_text": "I sell two bags rice give Mama Ngozi for sixty k",
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["amount_ngn"], 60000)
        self.assertEqual(len(self.client.get("/entries?type=credit_sale").json()), 1)
        self.assertEqual(self.client.get("/entries?type=expense").json(), [])

    def test_customer_balance_uses_recorded_payments(self) -> None:
        self.client.post(
            "/entries",
            json={"type": "credit_sale", "amount_ngn": 60000, "customer": "Mama Ngozi"},
        )
        self.client.post(
            "/entries",
            json={"type": "payment_received", "amount_ngn": 30000, "customer": "mama ngozi"},
        )

        customers = self.client.get("/customers").json()
        self.assertEqual(len(customers), 1)
        self.assertEqual(customers[0]["amount_owed_ngn"], 30000)
        self.assertEqual(customers[0]["open_credit_sales"], 1)

        answer = self.client.post("/ask", json={"question": "Who owes me?"}).json()
        self.assertEqual(answer["customers"][0]["name"], "Mama Ngozi")
        self.assertIn("₦30,000", answer["answer"])

    def test_credit_sale_requires_customer(self) -> None:
        response = self.client.post(
            "/entries", json={"type": "credit_sale", "amount_ngn": 5000}
        )
        self.assertEqual(response.status_code, 422)

    def test_health_check(self) -> None:
        self.assertEqual(self.client.get("/health").json(), {"status": "ok"})

    def test_message_extraction_saves_structured_record(self) -> None:
        def extractor(**kwargs: dict) -> dict:
            self.assertIn("customers", kwargs["context"])
            return {
                "status": "recorded",
                "entry": {
                    "type": "credit_sale",
                    "item": "rice",
                    "quantity": 2,
                    "unit": "bags",
                    "amount_ngn": 60000,
                    "customer": "Mama Ngozi",
                    "confidence": 0.93,
                },
            }

        temp_client = TestClient(create_app(Path(self.temp_dir.name) / "message.sqlite3", extractor))
        try:
            response = temp_client.post(
                "/messages",
                json={"text": "I give Mama Ngozi two bags rice on credit for 60k", "conversation_id": "trader-1"},
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "recorded")
            self.assertEqual(response.json()["entry"]["raw_text"], "I give Mama Ngozi two bags rice on credit for 60k")
            self.assertEqual(len(temp_client.get("/entries").json()), 1)
        finally:
            temp_client.close()

    def test_message_clarification_resumes_original_message(self) -> None:
        seen_contexts = []
        def extractor(*, text: str, context: dict) -> dict:
            seen_contexts.append((text, context))
            if len(seen_contexts) == 1:
                return {
                    "status": "needs_clarification",
                    "missing_fields": ["amount_ngn"],
                    "question": "How much did she pay?",
                }
            return {
                "status": "recorded",
                "entry": {
                    "type": "credit_sale",
                    "item": "rice",
                    "quantity": 2,
                    "unit": "bags",
                    "amount_ngn": 60000,
                    "customer": "Mama Ngozi",
                },
            }

        temp_client = TestClient(create_app(Path(self.temp_dir.name) / "clarification.sqlite3", extractor))
        try:
            first = temp_client.post("/messages", json={"text": "I give Mama Ngozi two bags rice", "conversation_id": "trader-2"})
            self.assertEqual(first.json()["status"], "needs_clarification")
            second = temp_client.post("/messages", json={"text": "na 60k", "conversation_id": "trader-2"})
            self.assertEqual(second.json()["status"], "recorded")
            self.assertEqual(seen_contexts[1][1]["pending_message"], "I give Mama Ngozi two bags rice")
            self.assertEqual(temp_client.get("/entries").json()[0]["raw_text"], "I give Mama Ngozi two bags rice")
        finally:
            temp_client.close()

    def test_correction_updates_last_record_and_preserves_revision(self) -> None:
        def extractor(*, text: str, context: dict) -> dict:
            if text.startswith("No be"):
                self.assertEqual(context["last_entry"]["quantity"], 2)
                return {
                    "status": "corrected",
                    "entry": {
                        "type": "credit_sale",
                        "item": "rice",
                        "quantity": 4,
                        "unit": "bags",
                        "amount_ngn": 60000,
                        "customer": "Mama Ngozi",
                    },
                }
            return {
                "status": "recorded",
                "entry": {"type": "credit_sale", "item": "rice", "quantity": 2, "unit": "bags", "amount_ngn": 60000, "customer": "Mama Ngozi"},
            }

        temp_client = TestClient(create_app(Path(self.temp_dir.name) / "correction.sqlite3", extractor))
        try:
            created = temp_client.post("/messages", json={"text": "two bags rice for 60k on credit", "conversation_id": "trader-3"}).json()
            corrected = temp_client.post("/messages", json={"text": "No be 2 bags, na 4 bags", "conversation_id": "trader-3"}).json()
            self.assertEqual(corrected["status"], "corrected")
            self.assertEqual(corrected["entry"]["id"], created["entry"]["id"])
            self.assertEqual(corrected["entry"]["quantity"], 4)
            self.assertEqual(len(temp_client.get("/entries").json()), 1)
        finally:
            temp_client.close()

    def test_correcting_tracked_sale_reconciles_stock_and_cost(self) -> None:
        def extractor(*, text: str, context: dict) -> dict:
            if text.startswith("No be"):
                self.assertEqual(context["last_entry"]["quantity"], 2)
            quantity = 4 if text.startswith("No be") else 2
            return {
                "status": "corrected" if text.startswith("No be") else "recorded",
                "entry": {
                    "type": "sale",
                    "item": "rice",
                    "quantity": quantity,
                    "unit": "bags",
                    "amount_ngn": 60000,
                    "confidence": 0.9,
                },
            }

        temp_client = TestClient(create_app(Path(self.temp_dir.name) / "tracked-correction.sqlite3", extractor))
        try:
            temp_client.post("/inventory/stock-in", json={"item": "rice", "quantity": 10, "unit": "bags", "unit_cost_ngn": 20000})
            created = temp_client.post("/messages", json={"text": "I sell 2 bags rice for 60k", "conversation_id": "trader-stock"}).json()
            corrected = temp_client.post("/messages", json={"text": "No be 2 bags, na 4 bags", "conversation_id": "trader-stock"}).json()
            self.assertEqual(corrected["entry"]["id"], created["entry"]["id"])
            self.assertEqual(corrected["entry"]["cost_of_goods_ngn"], 80000)
            self.assertEqual(temp_client.get("/inventory").json()[0]["quantity_on_hand"], 6)
        finally:
            temp_client.close()

    def test_message_without_provider_key_fails_clearly(self) -> None:
        temp_client = TestClient(create_app(Path(self.temp_dir.name) / "unconfigured.sqlite3"))
        try:
            response = temp_client.post(
                "/messages",
                json={"text": "I sell rice for 10k", "conversation_id": "trader-unconfigured"},
            )
            self.assertEqual(response.status_code, 503)
            self.assertIn("OPENAI_API_KEY", response.json()["detail"])
        finally:
            temp_client.close()

    def test_stock_in_sale_and_profit_report(self) -> None:
        stock = self.client.post(
            "/inventory/stock-in",
            json={
                "item": "rice",
                "quantity": 10,
                "unit": "bags",
                "unit_cost_ngn": 20000,
                "reorder_level": 2,
            },
        )
        self.assertEqual(stock.status_code, 201)
        self.assertEqual(stock.json()["quantity_on_hand"], 10)

        sale = self.client.post(
            "/entries",
            json={
                "type": "sale",
                "item": "rice",
                "quantity": 2,
                "unit": "bags",
                "amount_ngn": 60000,
            },
        )
        self.assertEqual(sale.status_code, 201)
        self.assertEqual(sale.json()["cost_of_goods_ngn"], 40000)
        self.assertEqual(self.client.get("/inventory").json()[0]["quantity_on_hand"], 8)

        self.client.post(
            "/entries",
            json={"type": "expense", "item": "Transport", "amount_ngn": 5000},
        )
        report = self.client.get("/reports/profit").json()
        self.assertEqual(report["sales_ngn"], 60000)
        self.assertEqual(report["expenses_ngn"], 5000)
        self.assertEqual(report["cost_of_goods_ngn"], 40000)
        self.assertEqual(report["estimated_profit_ngn"], 15000)
        self.assertEqual(report["uncosted_sales_count"], 0)

    def test_sale_cannot_reduce_stock_below_zero(self) -> None:
        self.client.post(
            "/inventory/stock-in",
            json={"item": "beans", "quantity": 1, "unit": "bag", "unit_cost_ngn": 25000},
        )
        response = self.client.post(
            "/entries",
            json={"type": "sale", "item": "beans", "quantity": 2, "unit": "bag", "amount_ngn": 50000},
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.client.get("/entries").json(), [])
        self.assertEqual(self.client.get("/inventory").json()[0]["quantity_on_hand"], 1)

    def test_untracked_sale_is_flagged_in_profit_report(self) -> None:
        self.client.post(
            "/entries",
            json={"type": "sale", "item": "garri", "quantity": 1, "unit": "measure", "amount_ngn": 7000},
        )

        report = self.client.get("/reports/profit").json()
        self.assertEqual(report["sales_ngn"], 7000)
        self.assertEqual(report["uncosted_sales_count"], 1)

    def test_existing_ledger_database_migrates_without_losing_entries(self) -> None:
        self.client.close()
        legacy_path = Path(self.temp_dir.name) / "legacy.sqlite3"
        with closing(sqlite3.connect(legacy_path)) as connection:
            connection.execute(
                """
                CREATE TABLE entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT NOT NULL,
                    item TEXT,
                    quantity REAL,
                    unit TEXT,
                    amount_ngn INTEGER NOT NULL,
                    customer TEXT,
                    due_date TEXT,
                    confidence REAL,
                    raw_text TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                INSERT INTO entries (type, item, amount_ngn, created_at)
                VALUES ('sale', 'rice', 60000, '2026-10-23T10:00:00+00:00')
                """
            )
            connection.commit()

        migrated_client = TestClient(create_app(legacy_path))
        try:
            entries = migrated_client.get("/entries").json()
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["item"], "rice")
            self.assertIsNone(entries[0]["cost_of_goods_ngn"])
        finally:
            migrated_client.close()


if __name__ == "__main__":
    unittest.main()