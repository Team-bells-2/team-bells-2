from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Any

from sqlalchemy.exc import IntegrityError

from app.ai.orchestrator import AIOrchestrator, InterpretationFailed
from app.ai.schemas import Interpretation
from app.customers.models import Customer
from app.customers.repositories.customer_repository import CustomerRepository
from app.inventory import services as inventory_services
from app.inventory.models import StockMovement
from app.inventory.repositories.inventory_repository import InventoryRepository
from app.ledger import services
from app.ledger.models import Entry, EntryEdit, PendingClarification
from app.ledger.repositories.clarification_repository import ClarificationRepository
from app.ledger.repositories.entry_repository import EntryRepository
from app.ledger.repositories.processed_message_repository import (
    ProcessedMessageRepository,
)
from app.ledger.schemas import EntryOut, ExtractedEntry, LedgerResult
from app.shared.errors import AppError
from app.shared.Infrastructure.llm.client import LLMError
from app.shared.Infrastructure.realtime.hub import EventPublisher
from app.shared.Infrastructure.SST.client import (
    SUPPORTED_AUDIO_TYPES,
    Transcriber,
    TranscriptionError,
)
from app.shared.matching import match_key
from app.shared.periods import LAGOS

# Outcome of resolving a customer mention: (kind, customer, detail).
#   ("ok", customer, None) | ("new", None, None) | ("none", None, None)
#   ("ambiguous", None, question) | ("confirm", None, candidate name)
Resolution = tuple[str, Customer | None, str | None]


class LedgerOrchestrator:
    """Ledger workflows. Each public method is one unit of work: everything it writes
    (entry, customer, alias, stock movement, clarification state, audit row, dedupe record)
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
        customer_link_confidence: float,
        customer_confirm_confidence: float,
        item_link_confidence: float,
        item_confirm_confidence: float,
        events: EventPublisher,
    ):
        self.entry_repository = entry_repository
        self.clarification_repository = clarification_repository
        self.customer_repository = customer_repository
        self.inventory_repository = inventory_repository
        self.processed_message_repository = processed_message_repository
        self.ai_orchestrator = ai_orchestrator
        self.transcriber = transcriber
        self.confidence_threshold = confidence_threshold
        self.customer_link_confidence = customer_link_confidence
        self.customer_confirm_confidence = customer_confirm_confidence
        self.item_link_confidence = item_link_confidence
        self.item_confirm_confidence = item_confirm_confidence
        self.events = events
        # Inventory items whose stock movement changed in the current unit of work (published after commit).
        self._stock_touched: set[int] = set()

    def handle_text_message(
        self, trader_id: int, client_message_id: str, text: str
    ) -> LedgerResult:
        """POST /messages (FR-S1): interpret, then save, correct, clarify or fall back. Retries replay (NFR-5)."""
        return self._handle(trader_id, client_message_id, text, transcript=None)

    def handle_voice_message(
        self, trader_id: int, client_message_id: str, audio: bytes, content_type: str
    ) -> LedgerResult:
        """Voice note (FR-S2): transcribe, then the text path. The transcript becomes raw_text."""
        replay = self._replay(trader_id, client_message_id)
        if replay is not None:
            return replay
        if content_type not in SUPPORTED_AUDIO_TYPES:
            raise AppError(
                415,
                "unsupported_audio",
                "Unsupported audio type. Use WAV, MP3, M4A, AAC, OGG, WebM or FLAC.",
            )
        if not audio:
            raise AppError(422, "empty_audio", "The voice note is empty.")
        try:
            transcript = self.transcriber.transcribe(audio, content_type)
        except TranscriptionError as error:
            raise AppError(
                502,
                "transcription_failed",
                "We couldn't hear that voice note. Please resend it or type the message.",
            ) from error
        return self._handle(
            trader_id, client_message_id, transcript, transcript=transcript
        )

    def submit_entry(
        self, trader_id: int, raw_text: str, extracted: ExtractedEntry
    ) -> LedgerResult:
        """Save a complete entry, or hold it and ask one question. A pending entry is completed by the next message."""
        try:
            result = self._submit_entry(trader_id, raw_text, extracted)
            self.entry_repository.commit()
        except Exception:
            self.entry_repository.rollback()
            raise
        return result

    def correct_last_entry(
        self, trader_id: int, changes: ExtractedEntry
    ) -> LedgerResult:
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
        rows = self.entry_repository.list_entries(
            trader_id, since, entry_type, limit, offset
        )
        return [
            services.to_entry_out(entry, customer_name) for entry, customer_name in rows
        ]  # pyright: ignore[reportAssignmentType]

    def _handle(
        self, trader_id: int, client_message_id: str, text: str, transcript: str | None
    ) -> LedgerResult:
        replay = self._replay(trader_id, client_message_id)
        if replay is not None:
            return replay
        pending = self.clarification_repository.get_pending(trader_id)
        kind = pending.partial_entry.get(services.PENDING_KIND) if pending else None
        if (
            pending
            and kind in services.CONFIRM_KINDS
            and (services.is_yes(text) or services.is_no(text))
        ):
            # A yes/no to our own question is read in code, without a model call (BR-L6).
            confirmed_pending = pending
            work: Callable[[], LedgerResult] = lambda: self._answer_confirmation(
                trader_id, text, confirmed_pending
            )
        else:
            interpretation, read_by_rules = self._interpret(trader_id, text)
            work = lambda: self._with_rules_note(self._route(trader_id, text, interpretation), read_by_rules)
        return self._process_once(
            trader_id,
            client_message_id,
            lambda: work().model_copy(update={"transcript": transcript}),
        )

    @staticmethod
    def _with_rules_note(result: LedgerResult, read_by_rules: bool) -> LedgerResult:
        """Tell the trader when the built-in rules read the message because the assistant was down (NFR-3)."""
        if not read_by_rules:
            return result
        return result.model_copy(update={"message": f"{result.message} {services.RULES_NOTE}"})

    def _replay(self, trader_id: int, client_message_id: str) -> LedgerResult | None:
        processed = self.processed_message_repository.get_processed(
            trader_id, client_message_id
        )
        return LedgerResult.model_validate(processed.response) if processed else None

    def _process_once(
        self, trader_id: int, client_message_id: str, work: Callable[[], LedgerResult]
    ) -> LedgerResult:
        """Run `work` and record the message as processed in the same transaction. Change events go out
        only after the commit, and only for newly processed messages (a replay changed nothing)."""
        self._stock_touched = set()
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
        self._publish_changes(trader_id, result)
        return result

    def _publish_changes(self, trader_id: int, result: LedgerResult) -> None:
        if result.entry is not None and result.status in {"saved", "corrected"}:
            event = "entry_saved" if result.status == "saved" else "entry_updated"
            self.events.publish(trader_id, event, result.entry)
        for item_id in sorted(self._stock_touched):
            item = self.inventory_repository.get_item(trader_id, item_id)
            if item is not None:
                quantity = self.inventory_repository.get_quantity_on_hand(item.id)
                self.events.publish(trader_id, "inventory_changed", inventory_services.to_item_out(item, quantity))
        self._stock_touched = set()

    def _interpret(self, trader_id: int, text: str) -> tuple[Interpretation | None, bool]:
        """The reading and whether the built-in rules made it (the provider was down). A None reading means
        the model's output was invalid twice (FR-S3); the trader is asked to repeat. A provider failure on a
        message the rules cannot read either is a 503."""
        try:
            return self.ai_orchestrator.interpret_or_rules(
                text, self._interpretation_context(trader_id)
            )
        except InterpretationFailed:
            return None, False
        except LLMError as error:
            raise AppError(
                503,
                "ai_unavailable",
                "The assistant is unavailable right now. Please try again in a moment.",
            ) from error

    def _interpretation_context(self, trader_id: int) -> dict[str, Any]:
        context: dict[str, Any] = {
            "today": datetime.now(LAGOS).date().isoformat(),
            "customers": self._customer_list(
                trader_id, self.customer_repository.list_aliases(trader_id)
            ),
            "items": [
                item.name
                for item, _ in self.inventory_repository.list_items_with_quantity(
                    trader_id
                )
            ],
        }
        pending = self.clarification_repository.get_pending(trader_id)
        if pending:
            context["pending"] = {
                "fields": services.entry_fields(pending.partial_entry),
                "question": pending.question,
            }
        last_entry = self.entry_repository.get_last_saved_entry(trader_id)
        if last_entry:
            context["last_entry"] = services.entry_snapshot(
                last_entry, self._customer_name(trader_id, last_entry)
            )
        return context

    def _route(
        self, trader_id: int, text: str, interpretation: Interpretation | None
    ) -> LedgerResult:
        if interpretation is None:
            return LedgerResult(
                status="clarify", message=services.NOT_UNDERSTOOD_MESSAGE
            )
        if interpretation.intent == "unknown":
            return LedgerResult(status="fallback", message=services.FALLBACK_MESSAGE)

        extracted = services.to_extracted(interpretation, datetime.now(LAGOS).date())
        has_pending = self.clarification_repository.get_pending(trader_id) is not None
        if interpretation.intent == "correction" and not has_pending:
            return self._correct_last_entry(trader_id, extracted)
        # A "correction" while an entry is pending changes that pending entry, so it merges like an answer.
        return self._submit_entry(trader_id, text, extracted)

    def _submit_entry(
        self, trader_id: int, raw_text: str, extracted: ExtractedEntry
    ) -> LedgerResult:
        pending = self.clarification_repository.get_pending(trader_id)
        partial: dict[str, Any] = dict(pending.partial_entry) if pending else {}
        if pending and services.starts_over(
            raw_text, extracted, services.entry_fields(partial)
        ):
            self.clarification_repository.delete_pending(pending)
            pending, partial = None, {}
        elif pending and partial.get(services.PENDING_KIND) in services.CONFIRM_KINDS:
            # Neither yes, no nor a new entry: repeat the question; nothing is saved.
            return LedgerResult(status="clarify", message=pending.question)

        texts: list[str] = [*partial.get(services.PENDING_TEXTS, []), raw_text]
        fields = services.merge_partial(partial, extracted)
        # The trader answering our own missing-field question is not gated on confidence again (BR-L4).
        answered_question = (
            pending is not None and partial.get(services.PENDING_KIND) == "missing"
        )
        return self._complete(
            trader_id,
            fields,
            texts,
            pending,
            check_confidence=not answered_question,
            item_checked=bool(partial.get(services.PENDING_ITEM_CHECKED)),
        )

    def _complete(
        self,
        trader_id: int,
        fields: dict[str, Any],
        texts: list[str],
        pending: PendingClarification | None,
        check_confidence: bool,
        confirmed: bool = False,
        item_checked: bool = False,
    ) -> LedgerResult:
        """Ask for what is missing, confirm a low-confidence reading, match the item to inventory,
        resolve the customer, then save. One question at a time."""
        if services.missing_fields(fields):
            return self._hold(
                trader_id, fields, texts, services.missing_question(fields), "missing"
            )

        complete = ExtractedEntry.model_validate(fields)
        if check_confidence and services.is_low_confidence(
            complete.confidence, self.confidence_threshold
        ):
            return self._hold(
                trader_id,
                fields,
                texts,
                services.confirmation_question(fields),
                "confirm_entry",
            )

        if not item_checked:
            candidate = self._match_item(trader_id, fields, " ".join(texts))
            if candidate is not None:
                return self._hold(
                    trader_id,
                    fields,
                    texts,
                    f"Do you mean {candidate}?",
                    "confirm_item",
                    candidate=candidate,
                    mention=fields.get("item"),
                )

        kind, customer, detail = self._resolve_customer(
            trader_id, complete.customer, " ".join(texts)
        )
        if kind == "ambiguous" and detail:
            fields.pop("customer", None)
            return self._hold(trader_id, fields, texts, detail, "missing", item_checked=True)
        if kind == "confirm" and detail:
            return self._hold(
                trader_id,
                fields,
                texts,
                f"Do you mean {detail}?",
                "confirm_customer",
                candidate=detail,
                mention=complete.customer,
                item_checked=True,
            )
        if kind == "new" and complete.customer:
            customer = self._create_customer(trader_id, complete.customer)
        return self._save_entry(trader_id, fields, texts, customer, pending, confirmed)

    def _answer_confirmation(
        self, trader_id: int, text: str, pending: PendingClarification
    ) -> LedgerResult:
        """Yes/no to "Just to confirm ...?" or "Do you mean X?" (BR-L6)."""
        partial = dict(pending.partial_entry)
        fields = services.entry_fields(partial)
        texts = [*partial.get(services.PENDING_TEXTS, []), text]

        if partial.get(services.PENDING_KIND) == "confirm_entry":
            if services.is_no(text):
                self.clarification_repository.delete_pending(pending)
                return LedgerResult(
                    status="fallback", message=services.NOT_SAVED_MESSAGE
                )
            return self._complete(
                trader_id,
                fields,
                texts,
                pending,
                check_confidence=False,
                confirmed=True,
            )

        candidate = str(partial.get(services.PENDING_CANDIDATE, ""))
        mention = partial.get(services.PENDING_MENTION)
        if partial.get(services.PENDING_KIND) == "confirm_item":
            # Yes: the inventory item. No: keep the trader's own name (saved as not in inventory).
            if services.is_yes(text):
                fields["item"] = candidate
            return self._complete(
                trader_id,
                fields,
                texts,
                pending,
                check_confidence=False,
                confirmed=True,
                item_checked=True,
            )

        customer = self.customer_repository.get_customer_by_name(trader_id, candidate)
        if services.is_yes(text) and customer is not None:
            if mention:
                self._add_alias(customer, str(mention))
        else:
            aliases = self.customer_repository.list_aliases(trader_id)
            others = [
                c
                for c in services.customers_named_in(text, aliases)
                if c.canonical_name != candidate
            ]
            if len(others) == 1:
                customer = others[0]
            elif mention:
                customer = self._create_customer(trader_id, str(mention))
            else:
                fields.pop("customer", None)
                return self._hold(
                    trader_id,
                    fields,
                    texts,
                    services.WHICH_CUSTOMER_QUESTION,
                    "missing",
                )
        fields["customer"] = customer.canonical_name
        return self._save_entry(
            trader_id, fields, texts, customer, pending, confirmed=True
        )

    def _save_entry(
        self,
        trader_id: int,
        fields: dict[str, Any],
        texts: list[str],
        customer: Customer | None,
        pending: PendingClarification | None,
        confirmed: bool,
    ) -> LedgerResult:
        complete = ExtractedEntry.model_validate(fields)
        confidence = complete.confidence
        if confirmed:
            # The trader confirmed the reading, so it is no longer a low-confidence guess.
            confidence = max(confidence or 0.0, self.confidence_threshold)
        entry = self.entry_repository.create_entry(
            Entry(
                trader_id=trader_id,
                customer_id=customer.id if customer else None,
                type=complete.type,
                item=complete.item,
                quantity=complete.quantity,
                unit=complete.unit,
                amount_ngn=complete.amount_ngn,
                # Only credit sales are due later (BR-A2).
                due_date=complete.due_date if complete.type == "credit_sale" else None,
                confidence=confidence,
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

    def _correct_last_entry(
        self, trader_id: int, changes: ExtractedEntry
    ) -> LedgerResult:
        entry = self.entry_repository.get_last_saved_entry(trader_id)
        if entry is None:
            raise AppError(
                409, "no_entry_to_correct", "There is no saved entry to correct."
            )

        old_customer = (
            self.customer_repository.get_customer_by_id(trader_id, entry.customer_id)
            if entry.customer_id
            else None
        )
        old_values = services.entry_snapshot(
            entry, old_customer.canonical_name if old_customer else None
        )

        customer = old_customer
        if changes.customer is not None:
            kind, resolved, detail = self._resolve_customer(
                trader_id, changes.customer, changes.customer
            )
            if kind == "ambiguous":
                raise AppError(
                    422,
                    "ambiguous_customer",
                    detail or services.WHICH_CUSTOMER_QUESTION,
                )
            if kind == "confirm":
                raise AppError(
                    422,
                    "ambiguous_customer",
                    f"Do you mean {detail}? Please use the full name.",
                )
            customer = resolved or self._create_customer(trader_id, changes.customer)
        if changes.item is not None:
            changes = changes.model_copy(
                update={"item": self._linked_item(trader_id, changes.item, changes.item, entry.type)}
            )
        for field in (
            "type",
            "item",
            "quantity",
            "unit",
            "amount_ngn",
            "due_date",
            "confidence",
        ):
            value = getattr(changes, field)
            if value is not None:
                setattr(entry, field, value)
        entry.customer_id = customer.id if customer else None

        customer_name = customer.canonical_name if customer else None
        fields_after = {**old_values, "type": entry.type, "customer": customer_name}
        if services.missing_fields(fields_after):
            raise AppError(
                422, "incomplete_correction", services.missing_question(fields_after)
            )

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

    def _hold(
        self,
        trader_id: int,
        fields: dict[str, Any],
        texts: list[str],
        question: str,
        kind: str,
        candidate: str | None = None,
        mention: str | None = None,
        item_checked: bool = False,
    ) -> LedgerResult:
        partial: dict[str, Any] = {
            **fields,
            services.PENDING_TEXTS: texts,
            services.PENDING_KIND: kind,
        }
        if item_checked or kind == "confirm_item":
            partial[services.PENDING_ITEM_CHECKED] = True
        if candidate is not None:
            partial[services.PENDING_CANDIDATE] = candidate
            partial[services.PENDING_MENTION] = mention
        self.clarification_repository.save_pending(trader_id, partial, question)
        return LedgerResult(status="clarify", message=question)

    def _match_item(self, trader_id: int, fields: dict[str, Any], text: str) -> str | None:
        """FR-S25: item name first (match_key), then the model against the trader's inventory.
        A sure match replaces fields["item"] with the inventory name; an unsure one is returned as the
        candidate to confirm; otherwise the name stays as said (not in inventory)."""
        item, entry_type = fields.get("item"), fields.get("type")
        if not item or entry_type not in services.STOCK_TYPES:
            return None
        if self.inventory_repository.get_item_by_name(trader_id, item) is not None:
            return None
        names = [stocked.name for stocked, _ in self.inventory_repository.list_items_with_quantity(trader_id)]
        name, confidence = self.ai_orchestrator.match_item(item, text, names)
        if name and confidence >= self.item_link_confidence:
            fields["item"] = name
            return None
        if name and confidence >= self.item_confirm_confidence:
            return name
        return None

    def _linked_item(self, trader_id: int, item: str, text: str, entry_type: str) -> str:
        """For corrections, which cannot ask: the inventory name only when the model is sure."""
        fields: dict[str, Any] = {"item": item, "type": entry_type}
        sure_only = self._match_item(trader_id, fields, text)
        return item if sure_only is not None else fields["item"]

    def _resolve_customer(
        self, trader_id: int, mention: str | None, text: str
    ) -> Resolution:
        """FR-S9 / BR-L5: alias table first (aliases found in the message), then the canonical name,
        then the model against the trader's customer list."""
        if not mention:
            return "none", None, None
        aliases = self.customer_repository.list_aliases(trader_id)
        named = services.customers_named_in(f"{text} {mention}", aliases)
        if len(named) == 1:
            return "ok", named[0], None
        if len(named) > 1:
            exact = [
                c
                for c in named
                if c.canonical_name.casefold() == mention.strip().casefold()
            ]
            if len(exact) == 1:
                return "ok", exact[0], None
            return (
                "ambiguous",
                None,
                services.ambiguous_customer_question([c.canonical_name for c in named]),
            )

        existing = self.customer_repository.get_customer_by_name(trader_id, mention)
        if existing is not None:
            return "ok", existing, None

        known = self._customer_list(trader_id, aliases)
        if known:
            name, confidence = self.ai_orchestrator.match_customer(mention, text, known)
            if name and confidence >= self.customer_link_confidence:
                matched = self.customer_repository.get_customer_by_name(trader_id, name)
                if matched is not None:
                    self._add_alias(matched, mention)
                    return "ok", matched, None
            if name and confidence >= self.customer_confirm_confidence:
                return "confirm", None, name
        return "new", None, None

    def _customer_list(
        self, trader_id: int, aliases: Sequence[Any]
    ) -> list[dict[str, Any]]:
        """Each customer's name and other aliases, for the model's matching (BR-A7 checks its answer)."""
        by_customer: dict[int, list[str]] = {}
        for alias, customer in aliases:
            if alias.casefold() != customer.canonical_name.casefold():
                by_customer.setdefault(customer.id, []).append(alias)
        return [
            {
                "name": customer.canonical_name,
                "aliases": by_customer.get(customer.id, []),
            }
            for customer in self.customer_repository.list_customers(trader_id)
        ]

    def _create_customer(self, trader_id: int, name: str) -> Customer:
        """A new customer also gets its own name as an alias, so later messages find it (BR-L7)."""
        customer = self.customer_repository.create_customer(
            trader_id, " ".join(name.split())
        )
        self._add_alias(customer, customer.canonical_name)
        return customer

    def _add_alias(self, customer: Customer, alias: str) -> None:
        alias = " ".join(alias.split())
        if alias and not self.customer_repository.alias_exists(customer.id, alias):
            self.customer_repository.add_alias(customer.id, alias)

    def _customer_name(self, trader_id: int, entry: Entry) -> str | None:
        if entry.customer_id is None:
            return None
        customer = self.customer_repository.get_customer_by_id(
            trader_id, entry.customer_id
        )
        return customer.canonical_name if customer else None

    def _apply_stock_effect(self, trader_id: int, entry: Entry) -> list[Any]:
        """Keep the entry's single stock movement in line with the entry (FR-S25, S26; BR-L9).
        Stock only changes through these rules; model output cannot act on inventory directly (NFR-1).
        A sale larger than the stock on hand, or in a different unit, is saved and flagged "check_stock",
        with no movement. Item and unit names are compared with match_key.
        """
        item = (
            self.inventory_repository.get_item_by_name(trader_id, entry.item)
            if entry.item
            else None
        )
        existing = self.inventory_repository.get_movement_for_entry(entry.id)
        warning: str | None = None
        if item is not None and entry.unit is None and entry.quantity is not None:
            entry.unit = item.unit
        if entry.item and item is None and entry.type in services.SALE_TYPES:
            warning = "not_in_inventory"

        effect = (
            services.stock_effect(entry.type, entry.quantity)
            if item is not None
            else None
        )
        if item is not None and effect is not None and entry.unit and match_key(entry.unit) != match_key(item.unit):
            # A different unit cannot be counted against this item's stock ("cups" vs "bag").
            warning, effect = "check_stock", None
        if item is not None and effect is not None and effect[1] == "sale":
            available = self.inventory_repository.get_quantity_on_hand(item.id)
            if existing and existing.inventory_item_id == item.id:
                available -= existing.quantity_change
            if -effect[0] > available:
                warning, effect = "check_stock", None

        entry.inventory_item_id = item.id if item is not None else None
        entry.stock_warning = warning
        if existing is not None:
            self._stock_touched.add(existing.inventory_item_id)  # the old item, if the correction moved it
        if item is not None and effect is not None:
            self._stock_touched.add(item.id)
        if item is None or effect is None:
            if existing:
                self.inventory_repository.delete_movement(existing)
        elif existing:
            existing.inventory_item_id = item.id
            existing.quantity_change, existing.reason = effect
        else:
            change, reason = effect
            self.inventory_repository.add_movement(
                StockMovement(
                    inventory_item_id=item.id,
                    entry_id=entry.id,
                    quantity_change=change,
                    reason=reason,
                )
            )
        return [warning] if warning else []
