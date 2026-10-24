from sqlalchemy import delete, func, select

from app.chat.models import ChatMessage
from app.consent.models import AccessLog, AccessRequest, AccessToken
from app.customers.models import Customer, CustomerAlias
from app.inventory.models import InventoryItem, StockMovement
from app.ledger.models import Entry, EntryEdit, PendingClarification, ProcessedMessage
from app.onboarding.models import Location, Trader, TraderSession
from app.shared.Infrastructure.db.base_repository import BaseRepository
from app.suggestions.models import Supplier

# Every table holding trader data, children before parents, so a reset needs no database cascades.
_TRADER_TABLES = (
    ChatMessage, AccessLog, AccessToken, AccessRequest, StockMovement, EntryEdit, Entry, PendingClarification,
    ProcessedMessage, CustomerAlias, Customer, InventoryItem, TraderSession, Trader,
)
_SEED_LOCK_ID = 0x4F4A415F53454544


class SeedRepository(BaseRepository):
    def acquire_seed_lock(self) -> None:
        if self.db.get_bind().dialect.name == "postgresql":
            self.db.execute(select(func.pg_advisory_xact_lock(_SEED_LOCK_ID)))

    def location_exists(self, name: str) -> bool:
        return self.db.scalar(select(Location.id).where(Location.name == name)) is not None

    def supplier_exists(self, name: str) -> bool:
        return self.db.scalar(select(Supplier.id).where(Supplier.name == name)) is not None

    def add(self, instance: object) -> None:
        self.db.add(instance)
        self.db.flush()

    def delete_trader_data(self) -> None:
        """All traders and everything they own; locations and supplier data stay."""
        for table in _TRADER_TABLES:
            self.db.execute(delete(table))
        self.db.flush()
