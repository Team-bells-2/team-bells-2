from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Any

from sqlalchemy.exc import IntegrityError

from app.ai.orchestrator import AIOrchestrator, InterpretationFailed
from app.ai.schemas import Interpretation
from app.customers.models import Customer
from app.customers.repositories.customer_repository import CustomerRepository
from app.inventory.models import StockMovement
from app.inventory.repositories.inventory_repository import InventoryRepository
from app.ledger import services
from app.ledger.models import Entry, EntryEdit
from app.ledger.repositories.clarification_repository import ClarificationRepository
from app.ledger.repositories.entry_repository import EntryRepository
from app.ledger.repositories.processed_message_repository import ProcessedMessageRepository
from app.ledger.schemas import EntryOut, ExtractedEntry, LedgerResult
from app.shared.errors import AppError
from app.shared.Infrastructure.llm.client import LLMError
from app.shared.Infrastructure.SST.client import SUPPORTED_AUDIO_TYPES, Transcriber, TranscriptionError
from app.shared.periods import LAGOS


class LedgerOrchestrator:
    """Ledger workflows. Each public method is one unit of work: everything it writes
    (entry, customer, stock movement, clarification state, audit row, dedupe record)
    commits together or not at all (NFR-3)."""

    def __init__(
        self,
        entry_repository: EntryRepository,
        clarification_repository: ClarificationRepository,
        customer_repository: CustomerRepository,
        inventory_repository: InventoryRepository,
        processed_message_repository: ProcessedMessageRepository,
        ai_orchestrator: AIOrchestrator,
        transcriber: Transcriber,
        confidence_threshold: float,
    ):
        self.entry_repository = entry_repository
        self.clarification_repository = clarification_repository
        self.customer_repository = customer_repository
        self.inventory_repository = inventory_repository
        self.processed_message_repository = processed_message_repository
        self.ai_orchestrator = ai_orchestrator
        self.transcriber = transcriber
        self.confidence_threshold = confidence_threshold

    def handle_text_message(self, trader_id: int, client_message_id: str, text: str) -> LedgerResult:
        """POST /messages (FR-S1): interpret, then save, correct, clarify or fall back. Retries replay (NFR-5)."""
        replay = self._replay(trader_id, client_message_id)
        if replay is not None:
            return replay
        interpretation = self._interpret(trader_id, text)
        return self._process_once(
            trader_id, client_message_id, lambda: self._route(trader_id, text, interpretation)
        )

    def handle_voice_message(
        self, trader_id: int, client_message_id: str, audio: bytes, content_type: str
    ) -> LedgerResult:
        """Voice note (FR-S2): transcribe, then the text path. The transcript becomes raw_text."""
        replay = self._replay(trader_id, client_message_id)
        if replay is not None:
            return replay
        if content_type not in SUPPORTED_AUDIO_TYPES:
            raise AppError(415, "unsupported_audio", "Unsupported audio type. Use WAV, MP3, M4A, AAC, OGG, WebM or FLAC.")
        if not audio:
            raise AppError(422, "empty_audio", "The voice note is empty.")
        try:
            transcript = self.transcriber.transcribe(audio, content_type)
        except TranscriptionError as error:
            raise AppError(
                502, "transcription_failed", "We couldn't hear that voice note. Please resend it or type the message."
            ) from error
        interpretation = self._interpret(trader_id, transcript)
        result = self._process_once(
            trader_id,
            client_message_id,
            lambda: self._route(trader_id, transcript, interpretation).model_copy(update={"transcript": transcript}),
        )
        return result

    def submit_entry(
        self,
        trader_id: int,
        raw_text: str,
        extracted: ExtractedEntry,
        question: str | None = None,
    ) -> LedgerResult:
        """Save a complete entry, or hold it and ask one question. A pending entry is completed by the next message."""
        try:
            result = self._submit_entry(trader_id, raw_text, extracted, question)
            self.entry_repository.commit()
        except Exception:
            self.entry_repository.rollback()
            raise
        return result

    def correct_last_entry(self, trader_id: int, changes: ExtractedEntry) -> LedgerResult:
        """Update the trader's last saved entry in place and record the change (FR-S6)."""
        try:
            result = self._correct_last_entry(trader_id, changes)
            self.entry_repository.commit()
        except Exception:
            self.entry_repository.rollback()
            raise
        return result

    def list_entries(
        self,
        trader_id: int,
        since: datetime | None,
        entry_type: str | None,
        limit: int,
        offset: int,
    ) -> Sequence[EntryOut]:
        rows = self.entry_repository.list_entries(trader_id, since, entry_type, limit, offset)
        return [services.to_entry_out(entry, customer_name) for entry, customer_name in rows]

    def _replay(self, trader_id: int, client_message_id: str) -> LedgerResult | None:
        processed = self.processed_message_repository.get_processed(trader_id, client_message_id)
        return LedgerResult.model_validate(processed.response) if processed else None

    def _process_once(
        self, trader_id: int, client_message_id: str, work: Callable[[], LedgerResult]
    ) -> LedgerResult:
        """Run `work` and record the message as processed in the same transaction."""
        try:
            result = work()
            self.processed_message_repository.add_processed(
                trader_id, client_message_id, result.model_dump(mode="json")
            )
            self.entry_repository.commit()
        except IntegrityError:
            # The same message was processed concurrently; discard ours and replay theirs.
            self.entry_repository.rollback()
            replay = self._replay(trader_id, client_message_id)
            if replay is None:
                raise
            return replay
        except Exception:
            self.entry_repository.rollback()
            raise
        return result

    def _interpret(self, trader_id: int, text: str) -> Interpretation | None:
        """None means the model's output was invalid twice (FR-S3); the trader is asked to repeat."""
        try:
            return self.ai_orchestrator.interpret_message(text, self._interpretation_context(trader_id))
        except InterpretationFailed:
            return None
        except LLMError as error:
            raise AppError(
                503, "ai_unavailable", "The assistant is unavailable right now. Please try again in a moment."
            ) from error

    def _interpretation_context(self, trader_id: int) -> dict[str, Any]:
        context: dict[str, Any] = {
            "today": datetime.now(LAGOS).date().isoformat(),
            "customers": [customer.canonical_name for customer in self.customer_repository.list_customers(trader_id)],
        }
        pending = self.clarification_repository.get_pending(trader_id)
        if pending:
            fields = {key: value for key, value in pending.partial_entry.items() if key != "raw_texts"}
            context["pending"] = {"fields": fields, "question": pending.question}
        last_entry = self.entry_repository.get_last_saved_entry(trader_id)
        if last_entry:
            customer = (
                self.customer_repository.get_customer_by_id(trader_id, last_entry.customer_id)
                if last_entry.customer_id
                else None
            )
            context["last_entry"] = services.entry_snapshot(last_entry, customer.canonical_name if customer else None)
        return context

    def _route(self, trader_id: int, text: str, interpretation: Interpretation | None) -> LedgerResult:
        if interpretation is None:
            return LedgerResult(status="clarify", message=services.NOT_UNDERSTOOD_MESSAGE)
        if interpretation.intent == "unknown":
            return LedgerResult(status="fallback", message=services.FALLBACK_MESSAGE)

        extracted = services.to_extracted(interpretation)
        has_pending = self.clarification_repository.get_pending(trader_id) is not None
        if interpretation.intent == "correction" and not has_pending:
            return self._correct_last_entry(trader_id, extracted)
        # A "correction" while an entry is pending changes that pending entry, so it merges like an answer.
        return self._submit_entry(trader_id, text, extracted, interpretation.question)

    def _submit_entry(
        self, trader_id: int, raw_text: str, extracted: ExtractedEntry, question: str | None
    ) -> LedgerResult:
        pending = self.clarification_repository.get_pending(trader_id)
        partial: dict[str, Any] = dict(pending.partial_entry) if pending else {}
        texts: list[str] = [*partial.pop("raw_texts", []), raw_text]
        fields = services.merge_partial(partial, extracted)

        missing = services.missing_fields(fields)
        if missing:
            return self._hold(trader_id, fields, texts, question or services.clarification_question(missing))

        complete = ExtractedEntry.model_validate(fields)
        if services.is_low_confidence(complete.confidence, self.confidence_threshold):
            return self._hold(trader_id, fields, texts, services.confirmation_question(fields))

        customer, ambiguity = self._resolve_customer(trader_id, complete.customer)
        if ambiguity:
            fields.pop("customer", None)
            return self._hold(trader_id, fields, texts, ambiguity)

        entry = self.entry_repository.create_entry(
            Entry(
                trader_id=trader_id,
                customer_id=customer.id if customer else None,
                type=complete.type,
                item=complete.item,
                quantity=complete.quantity,
                unit=complete.unit,
                amount_ngn=complete.amount_ngn,
                due_date=complete.due_date,
                confidence=complete.confidence,
                raw_text=" | ".join(texts),
            )
        )
        flags = self._apply_stock_effect(trader_id, entry)
        if pending:
            self.clarification_repository.delete_pending(pending)
        self.entry_repository.refresh(entry)

        customer_name = customer.canonical_name if customer else None
        return LedgerResult(
            status="saved",
            message=services.build_confirmation(entry, customer_name, corrected=False),
            entry=services.to_entry_out(entry, customer_name),
            flags=flags,
        )

    def _correct_last_entry(self, trader_id: int, changes: ExtractedEntry) -> LedgerResult:
        entry = self.entry_repository.get_last_saved_entry(trader_id)
        if entry is None:
            raise AppError(409, "no_entry_to_correct", "There is no saved entry to correct.")

        old_customer = (
            self.customer_repository.get_customer_by_id(trader_id, entry.customer_id) if entry.customer_id else None
        )
        old_values = services.entry_snapshot(entry, old_customer.canonical_name if old_customer else None)

        customer = old_customer
        if changes.customer is not None:
            customer, ambiguity = self._resolve_customer(trader_id, changes.customer)
            if ambiguity:
                raise AppError(422, "ambiguous_customer", ambiguity)
        for field in ("type", "item", "quantity", "unit", "amount_ngn", "due_date", "confidence"):
            value = getattr(changes, field)
            if value is not None:
                setattr(entry, field, value)
        entry.customer_id = customer.id if customer else None

        customer_name = customer.canonical_name if customer else None
        missing = services.missing_fields({**old_values, "type": entry.type, "customer": customer_name})
        if missing:
            raise AppError(422, "incomplete_correction", services.clarification_question(missing))

        flags = self._apply_stock_effect(trader_id, entry)
        self.entry_repository.add_edit(
            EntryEdit(
                entry_id=entry.id,
                old_values=old_values,
                new_values=services.entry_snapshot(entry, customer_name),
            )
        )
        self.entry_repository.refresh(entry)
        return LedgerResult(
            status="corrected",
            message=services.build_confirmation(entry, customer_name, corrected=True),
            entry=services.to_entry_out(entry, customer_name),
            flags=flags,
        )

    def _hold(self, trader_id: int, fields: dict[str, Any], texts: list[str], question: str) -> LedgerResult:
        self.clarification_repository.save_pending(trader_id, {**fields, "raw_texts": texts}, question)
        return LedgerResult(status="clarify", message=question)

    def _resolve_customer(self, trader_id: int, name: str | None) -> tuple[Customer | None, str | None]:
        """Alias table first, then canonical name, else a new customer (FR-S9).
        Returns (customer, question) where question is set only when the name is ambiguous."""
        if not name:
            return None, None
        by_alias = self.customer_repository.find_customers_by_alias(trader_id, name)
        if len(by_alias) > 1:
            return None, services.ambiguous_customer_question([c.canonical_name for c in by_alias])
        if by_alias:
            return by_alias[0], None
        existing = self.customer_repository.get_customer_by_name(trader_id, name)
        return existing or self.customer_repository.create_customer(trader_id, name), None

    def _apply_stock_effect(self, trader_id: int, entry: Entry) -> list[Any]:
        """Create, update or remove the entry's single stock movement so it matches the entry.
        Stock only changes through these rules; model output cannot act on inventory directly (NFR-1)."""
        flags: list[Any] = []
        item = self.inventory_repository.get_item_by_name(trader_id, entry.item) if entry.item else None
        if entry.item and item is None and entry.type in services.SALE_TYPES:
            flags.append("not_in_inventory")

        existing = self.inventory_repository.get_movement_for_entry(entry.id)
        effect = services.stock_effect(entry.type, entry.quantity)
        if item is None or effect is None:
            entry.inventory_item_id = None
            if existing:
                self.inventory_repository.delete_movement(existing)
            return flags

        change, reason = effect
        if reason == "sale":
            on_hand = self.inventory_repository.get_quantity_on_hand(item.id)
            if existing and existing.inventory_item_id == item.id:
                on_hand -= existing.quantity_change
            if -change > on_hand:
                flags.append("check_stock")

        entry.inventory_item_id = item.id
        if existing:
            existing.inventory_item_id = item.id
            existing.quantity_change = change
            existing.reason = reason
        else:
            self.inventory_repository.add_movement(
                StockMovement(inventory_item_id=item.id, entry_id=entry.id, quantity_change=change, reason=reason)
            )
        return flags
