"""Ledger workflows below the API (FR-S5, S6, S9, S25, S26, NFR-3).
Run: cd server && python -m unittest discover -s tests -t ."""

from decimal import Decimal

from sqlalchemy import func, select

from app.ai.orchestrator import AIOrchestrator
from app.customers.models import CustomerAlias
from app.customers.repositories.customer_repository import CustomerRepository
from app.inventory.repositories.inventory_repository import InventoryRepository
from app.inventory.models import StockMovement
from app.ledger.models import Entry, EntryEdit, PendingClarification
from app.ledger.orchestrator import LedgerOrchestrator
from app.ledger.repositories.clarification_repository import ClarificationRepository
from app.ledger.repositories.entry_repository import EntryRepository
from app.ledger.repositories.processed_message_repository import ProcessedMessageRepository
from app.ledger.schemas import ExtractedEntry
from app.shared.errors import AppError
from app.shared.Infrastructure.realtime.hub import hub
from tests.support import ApiTestCase, FakeLLM, FakeTranscriber

D = Decimal


class LedgerWorkflowTest(ApiTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.trader_id, self.headers = self.onboard()

    def ledger(self) -> LedgerOrchestrator:
        db = self.Session()
        return LedgerOrchestrator(
            EntryRepository(db),
            ClarificationRepository(db),
            CustomerRepository(db),
            InventoryRepository(db),
            ProcessedMessageRepository(db),
            AIOrchestrator(FakeLLM(), demo_mode=False),  # pyright: ignore[reportArgumentType]  (no replies queued: offline guess)
            FakeTranscriber(),
            0.7,
            0.85,
            0.5,
            0.85,
            0.5,
            hub,  # no sockets open in these tests, so publishing is a no-op
        )

    def count(self, model: type, *conditions: object) -> int:
        with self.Session() as db:
            return db.scalar(select(func.count()).select_from(model).where(*conditions)) or 0  # pyright: ignore[reportArgumentType]

    def test_clarify_then_complete_joins_raw_text_and_moves_stock(self) -> None:
        rice = self.add_stock(self.trader_id, "Rice", "10")
        result = self.ledger().submit_entry(
            self.trader_id,
            "I sell two bags and half",
            ExtractedEntry(type="sale", item="rice", quantity=D("2.5"), unit="bags"),
        )
        self.assertEqual((result.status, result.message), ("clarify", "How much did you collect for the 2.5 bags?"))
        self.assertEqual(self.count(Entry), 0)

        result = self.ledger().submit_entry(self.trader_id, "25k", ExtractedEntry(amount_ngn=D(25000)))
        self.assertEqual(result.status, "saved")
        assert result.entry is not None
        self.assertEqual(result.entry.raw_text, "I sell two bags and half | 25k")
        self.assertEqual(self.on_hand(rice), D("7.5"))
        self.assertEqual(self.count(PendingClarification), 0)

    def test_correction_updates_same_entry_and_same_movement_with_audit(self) -> None:
        rice = self.add_stock(self.trader_id, "Rice", "10")
        saved = self.ledger().submit_entry(
            self.trader_id, "sold 2.5 bags rice 25k",
            ExtractedEntry(type="sale", item="rice", quantity=D("2.5"), unit="bags", amount_ngn=D(25000)),
        )
        corrected = self.ledger().correct_last_entry(self.trader_id, ExtractedEntry(quantity=D(4)))
        assert saved.entry is not None and corrected.entry is not None
        self.assertEqual((corrected.status, corrected.entry.id), ("corrected", saved.entry.id))
        self.assertEqual(self.on_hand(rice), D(6))
        self.assertEqual(self.count(StockMovement, StockMovement.entry_id == saved.entry.id), 1)
        with self.Session() as db:
            edit = db.scalar(select(EntryEdit))
            assert edit is not None
            self.assertTrue(edit.old_values["quantity"].startswith("2.5"))
            self.assertTrue(edit.new_values["quantity"].startswith("4"))

    def test_alias_resolves_to_canonical_customer(self) -> None:
        self.ledger().submit_entry(
            self.trader_id, "Mama Ngozi 60k credit",
            ExtractedEntry(type="credit_sale", customer="Mama Ngozi", amount_ngn=D(60000)),
        )
        with self.Session() as db:
            customer = CustomerRepository(db).get_customer_by_name(self.trader_id, "Mama Ngozi")
            assert customer is not None
            db.add(CustomerAlias(customer_id=customer.id, alias="the rice woman"))
            db.commit()
        result = self.ledger().submit_entry(
            self.trader_id, "the rice woman don pay thirty k",
            ExtractedEntry(type="payment_received", customer="the rice woman", amount_ngn=D(30000)),
        )
        assert result.entry is not None
        self.assertEqual(result.entry.customer, "Mama Ngozi")

    def test_shared_alias_asks_which_customer_then_completes(self) -> None:
        with self.Session() as db:
            repository = CustomerRepository(db)
            for name in ("Mama Ngozi", "Mama Bisi"):
                db.add(CustomerAlias(customer_id=repository.create_customer(self.trader_id, name).id, alias="Mama"))
            db.commit()
        result = self.ledger().submit_entry(
            self.trader_id, "Mama pay 5k", ExtractedEntry(type="payment_received", customer="Mama", amount_ngn=D(5000))
        )
        self.assertEqual((result.status, result.message), ("clarify", "Do you mean Mama Bisi or Mama Ngozi?"))
        result = self.ledger().submit_entry(self.trader_id, "Mama Bisi", ExtractedEntry(customer="Mama Bisi"))
        assert result.entry is not None
        self.assertEqual((result.status, result.entry.customer), ("saved", "Mama Bisi"))

    def test_expense_on_stocked_item_restocks(self) -> None:
        rice = self.add_stock(self.trader_id, "Rice", "6")
        self.ledger().submit_entry(
            self.trader_id, "buy 5 bags rice 300k",
            ExtractedEntry(type="expense", item="rice", quantity=D(5), unit="bags", amount_ngn=D(300000)),
        )
        self.assertEqual(self.on_hand(rice), D(11))

    def test_expense_without_matching_item_changes_no_stock(self) -> None:
        rice = self.add_stock(self.trader_id, "Rice", "6")
        result = self.ledger().submit_entry(
            self.trader_id, "transport 40k", ExtractedEntry(type="expense", item="transport", amount_ngn=D(40000))
        )
        self.assertEqual((result.status, result.flags), ("saved", []))
        self.assertEqual(self.on_hand(rice), D(6))

    def test_oversell_is_saved_and_flagged_without_moving_stock(self) -> None:
        rice = self.add_stock(self.trader_id, "Rice", "2")
        result = self.ledger().submit_entry(
            self.trader_id, "sell 50 bags rice 2m",
            ExtractedEntry(type="sale", item="rice", quantity=D(50), unit="bags", amount_ngn=D(2000000)),
        )
        assert result.entry is not None
        self.assertEqual((result.status, result.flags, result.entry.stock_warning), ("saved", ["check_stock"], "check_stock"))
        self.assertEqual(self.on_hand(rice), D(2))

    def test_correction_that_oversells_removes_the_movement(self) -> None:
        rice = self.add_stock(self.trader_id, "Rice", "5")
        self.ledger().submit_entry(
            self.trader_id, "sold 2 bags rice 20k",
            ExtractedEntry(type="sale", item="rice", quantity=D(2), unit="bag", amount_ngn=D(20000)),
        )
        self.assertEqual(self.on_hand(rice), D(3))
        result = self.ledger().correct_last_entry(self.trader_id, ExtractedEntry(quantity=D(9)))
        self.assertEqual(result.flags, ["check_stock"])
        self.assertEqual(self.on_hand(rice), D(5))

    def test_entry_without_unit_takes_the_items_unit(self) -> None:
        self.add_stock(self.trader_id, "Rice", "5")
        result = self.ledger().submit_entry(
            self.trader_id, "sold 2 rice 20k", ExtractedEntry(type="sale", item="rice", quantity=D(2), amount_ngn=D(20000))
        )
        assert result.entry is not None
        self.assertEqual(result.entry.unit, "bag")

    def test_sale_of_untracked_item_is_flagged(self) -> None:
        result = self.ledger().submit_entry(
            self.trader_id, "sold beans 50k", ExtractedEntry(type="sale", item="beans", amount_ngn=D(50000))
        )
        self.assertEqual(result.flags, ["not_in_inventory"])

    def test_failed_write_rolls_back_everything(self) -> None:
        self.add_stock(self.trader_id, "Rice", "10")
        self.ledger().submit_entry(
            self.trader_id, "Chidi buy rice on credit",
            ExtractedEntry(type="credit_sale", customer="Chidi", item="rice", quantity=D(1)),
        )
        ledger = self.ledger()

        def fail(*_: object, **__: object) -> None:
            raise RuntimeError("database down")

        ledger.inventory_repository.add_movement = fail  # pyright: ignore[reportAttributeAccessIssue]
        with self.assertRaises(RuntimeError):
            ledger.submit_entry(self.trader_id, "20k", ExtractedEntry(amount_ngn=D(20000)))
        self.assertEqual(self.count(Entry), 0)
        with self.Session() as db:
            self.assertIsNone(CustomerRepository(db).get_customer_by_name(self.trader_id, "Chidi"))
        self.assertEqual(self.count(PendingClarification, PendingClarification.trader_id == self.trader_id), 1)

    def test_correction_without_an_entry_is_409(self) -> None:
        with self.assertRaises(AppError) as raised:
            self.ledger().correct_last_entry(self.trader_id, ExtractedEntry(quantity=D(1)))
        self.assertEqual((raised.exception.status_code, raised.exception.code), (409, "no_entry_to_correct"))
