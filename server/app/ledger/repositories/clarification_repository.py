from typing import Any

from sqlalchemy import select

from app.ledger.models import PendingClarification
from app.shared.Infrastructure.db.base_repository import BaseRepository


class ClarificationRepository(BaseRepository):
    def get_pending(self, trader_id: int) -> PendingClarification | None:
        return self.db.scalar(select(PendingClarification).where(PendingClarification.trader_id == trader_id))

    def save_pending(self, trader_id: int, partial_entry: dict[str, Any], question: str) -> PendingClarification:
        """Create or replace the trader's single pending clarification."""
        pending = self.get_pending(trader_id)
        if pending is None:
            pending = PendingClarification(trader_id=trader_id, partial_entry=partial_entry, question=question)
            self.db.add(pending)
        else:
            pending.partial_entry = partial_entry
            pending.question = question
        self.db.flush()
        return pending

    def delete_pending(self, pending: PendingClarification) -> None:
        self.db.delete(pending)
        self.db.flush()
