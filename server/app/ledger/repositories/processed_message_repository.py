from typing import Any

from sqlalchemy import select

from app.ledger.models import ProcessedMessage
from app.shared.Infrastructure.db.base_repository import BaseRepository


class ProcessedMessageRepository(BaseRepository):
    def get_processed(self, trader_id: int, client_message_id: str) -> ProcessedMessage | None:
        return self.db.scalar(
            select(ProcessedMessage).where(
                ProcessedMessage.trader_id == trader_id,
                ProcessedMessage.client_message_id == client_message_id,
            )
        )

    def add_processed(self, trader_id: int, client_message_id: str, response: dict[str, Any]) -> ProcessedMessage:
        processed = ProcessedMessage(trader_id=trader_id, client_message_id=client_message_id, response=response)
        self.db.add(processed)
        self.db.flush()
        return processed
