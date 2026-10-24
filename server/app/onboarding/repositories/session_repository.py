from datetime import datetime

from sqlalchemy import select

from app.onboarding.models import Trader, TraderSession
from app.shared.Infrastructure.db.base_repository import BaseRepository


class SessionRepository(BaseRepository):
    def create_session(
        self, trader_id: int, token_hash: str, expires_at: datetime
    ) -> TraderSession:
        session = TraderSession(
            trader_id=trader_id, token_hash=token_hash, expires_at=expires_at
        )
        self.db.add(session)
        self.db.flush()
        return session

    def get_session_by_token_hash(self, token_hash: str) -> TraderSession | None:
        return self.db.scalar(
            select(TraderSession).where(TraderSession.token_hash == token_hash)
        )

    def get_trader(self, trader_id: int) -> Trader | None:
        return self.db.get(Trader, trader_id)
