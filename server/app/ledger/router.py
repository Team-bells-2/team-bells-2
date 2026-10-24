from collections.abc import Sequence

from fastapi import APIRouter, Depends, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from starlette.datastructures import UploadFile

from app.ai.dependencies import get_ai_orchestrator
from app.ai.orchestrator import AIOrchestrator
from app.customers.dependencies import get_customer_repository
from app.customers.repositories.customer_repository import CustomerRepository
from app.inventory.dependencies import get_inventory_repository
from app.inventory.repositories.inventory_repository import InventoryRepository
from app.ledger.dependencies import (
    get_clarification_repository,
    get_entry_repository,
    get_processed_message_repository,
)
from app.ledger.orchestrator import LedgerOrchestrator
from app.ledger.repositories.clarification_repository import ClarificationRepository
from app.ledger.repositories.entry_repository import EntryRepository
from app.ledger.repositories.processed_message_repository import ProcessedMessageRepository
from app.ledger.schemas import EntryOut, EntryType, LedgerResult, MessageRequest
from app.onboarding.models import Trader
from app.onboarding.router import get_current_trader
from app.shared.env import settings
from app.shared.errors import AppError
from app.shared.Infrastructure.realtime.hub import EventPublisher, get_event_publisher
from app.shared.Infrastructure.SST.client import Transcriber, get_transcriber
from app.shared.periods import Period, period_start

router = APIRouter(tags=["ledger"])


def get_ledger_orchestrator(
    entry_repository: EntryRepository = Depends(get_entry_repository),
    clarification_repository: ClarificationRepository = Depends(get_clarification_repository),
    customer_repository: CustomerRepository = Depends(get_customer_repository),
    inventory_repository: InventoryRepository = Depends(get_inventory_repository),
    processed_message_repository: ProcessedMessageRepository = Depends(get_processed_message_repository),
    ai_orchestrator: AIOrchestrator = Depends(get_ai_orchestrator),
    transcriber: Transcriber = Depends(get_transcriber),
    events: EventPublisher = Depends(get_event_publisher),
) -> LedgerOrchestrator:
    return LedgerOrchestrator(
        entry_repository,
        clarification_repository,
        customer_repository,
        inventory_repository,
        processed_message_repository,
        ai_orchestrator,
        transcriber,
        settings.CONFIDENCE_THRESHOLD,
        settings.CUSTOMER_MATCH_LINK_CONFIDENCE,
        settings.CUSTOMER_MATCH_CONFIRM_CONFIDENCE,
        settings.ITEM_MATCH_LINK_CONFIDENCE,
        settings.ITEM_MATCH_CONFIRM_CONFIDENCE,
        events,
    )


@router.post("/messages", response_model=LedgerResult)
async def post_message(
    request: Request,
    trader: Trader = Depends(get_current_trader),
    orchestrator: LedgerOrchestrator = Depends(get_ledger_orchestrator),
) -> LedgerResult:
    """Text as JSON {text, client_message_id}, or a voice note as multipart form
    fields `audio` (file) and `client_message_id` (FR-S1, S2)."""
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("multipart/form-data"):
        # The form owns the upload's temporary file; leaving the block closes it.
        async with request.form() as form:
            audio = form.get("audio")
            client_message_id = form.get("client_message_id")
            if not isinstance(audio, UploadFile):
                raise AppError(422, "validation_error", "audio: a voice note file is required.")
            if not isinstance(client_message_id, str) or not 1 <= len(client_message_id.strip()) <= 64:
                raise AppError(422, "validation_error", "client_message_id: 1 to 64 characters required.")
            max_bytes = settings.STT_MAX_UPLOAD_MB * 1024 * 1024
            data = await audio.read(max_bytes + 1)
            if len(data) > max_bytes:
                raise AppError(
                    413, "audio_too_large", f"Voice notes must be {settings.STT_MAX_UPLOAD_MB} MB or smaller."
                )
            audio_type = (audio.content_type or "").split(";", maxsplit=1)[0].strip().lower()
        return await run_in_threadpool(
            orchestrator.handle_voice_message, trader.id, client_message_id.strip(), data, audio_type
        )

    try:
        body = MessageRequest.model_validate(await request.json())
    except ValidationError as error:
        raise RequestValidationError(error.errors()) from error
    except ValueError as error:
        raise AppError(422, "validation_error", "Send JSON {text, client_message_id} or a multipart voice note.") from error
    return await run_in_threadpool(orchestrator.handle_text_message, trader.id, body.client_message_id, body.text)


@router.get("/entries", response_model=list[EntryOut])
def list_entries(
    period: Period | None = Query(default=None),
    entry_type: EntryType | None = Query(default=None, alias="type"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    trader: Trader = Depends(get_current_trader),
    orchestrator: LedgerOrchestrator = Depends(get_ledger_orchestrator),
) -> Sequence[EntryOut]:
    since = period_start(period) if period else None
    return orchestrator.list_entries(trader.id, since, entry_type, limit, offset)
