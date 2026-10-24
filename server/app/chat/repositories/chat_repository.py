from collections.abc import Sequence

from sqlalchemy import select

from app.chat.models import ChatMessage
from app.shared.Infrastructure.db.base_repository import BaseRepository


class ChatRepository(BaseRepository):
    def has_turn(self, trader_id: int, client_message_id: str) -> bool:
        return (
            self.db.scalar(
                select(ChatMessage.id).where(
                    ChatMessage.trader_id == trader_id,
                    ChatMessage.client_message_id == client_message_id,
                )
            )
            is not None
        )

    def add_message(
        self,
        trader_id: int,
        role: str,
        text: str,
        entry_id: int | None = None,
        client_message_id: str | None = None,
    ) -> ChatMessage:
        message = ChatMessage(
            trader_id=trader_id, role=role, text=text, entry_id=entry_id, client_message_id=client_message_id
        )
        self.db.add(message)
        self.db.flush()
        return message

    def list_messages(self, trader_id: int, limit: int, before_id: int | None) -> Sequence[ChatMessage]:
        """The newest `limit` messages (older than `before_id` when given), newest first."""
        query = select(ChatMessage).where(ChatMessage.trader_id == trader_id)
        if before_id is not None:
            query = query.where(ChatMessage.id < before_id)
        return self.db.scalars(query.order_by(ChatMessage.id.desc()).limit(limit)).all()
