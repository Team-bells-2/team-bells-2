import logging

from app.chat.repositories.chat_repository import ChatRepository
from app.chat.schemas import ChatHistory, ChatMessageOut

logger = logging.getLogger(__name__)


class ChatOrchestrator:
    """Keeps the assistant chat per trader. A failed history write never fails the trader's
    message: the entry is already saved, so the error is logged and the turn is skipped."""

    def __init__(self, chat_repository: ChatRepository):
        self.chat_repository = chat_repository

    def record_turn(
        self,
        trader_id: int,
        trader_text: str,
        assistant_text: str,
        entry_id: int | None = None,
        client_message_id: str | None = None,
    ) -> None:
        try:
            # A retry of the same app message replays the original reply; store the turn once.
            if client_message_id is not None and self.chat_repository.has_turn(trader_id, client_message_id):
                return
            self.chat_repository.add_message(trader_id, "trader", trader_text, None, client_message_id)
            self.chat_repository.add_message(trader_id, "assistant", assistant_text, entry_id, client_message_id)
            self.chat_repository.commit()
        except Exception:
            self.chat_repository.rollback()
            logger.exception("chat history: could not store a turn for trader %s", trader_id)

    def history(self, trader_id: int, limit: int, before_id: int | None) -> ChatHistory:
        rows = self.chat_repository.list_messages(trader_id, limit + 1, before_id)
        has_more = len(rows) > limit
        newest_first = rows[:limit]
        return ChatHistory(
            messages=[ChatMessageOut.model_validate(row, from_attributes=True) for row in reversed(newest_first)],
            has_more=has_more,
        )
