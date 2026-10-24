from sqlalchemy import select

from app.onboarding.models import Trader, TraderSession
from app.shared.Infrastructure.db.base_repository import BaseRepository


class SessionRepository(BaseRepository):
    def create_session(self, trader_id: int, token_hash: str) -> TraderSession:
        session = TraderSession(trader_id=trader_id, token_hash=token_hash)
        self.db.add(session)
        self.db.flush()
        return session

    def get_trader_by_active_token_hash(self, token_hash: str) -> Trader | None:
        return self.db.scalar(
            select(Trader)
            .join(TraderSession, TraderSession.trader_id == Trader.id)
            .where(TraderSession.token_hash == token_hash, TraderSession.revoked_at.is_(None))
        )
