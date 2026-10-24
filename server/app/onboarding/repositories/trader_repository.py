from sqlalchemy import select

from app.onboarding.models import Trader
from app.shared.Infrastructure.db.base_repository import BaseRepository


class TraderRepository(BaseRepository):
    def get_trader_by_phone(self, phone: str) -> Trader | None:
        return self.db.scalar(select(Trader).where(Trader.phone == phone))

    def create_trader(self, trader: Trader) -> Trader:
        self.db.add(trader)
        self.db.flush()
        return trader
