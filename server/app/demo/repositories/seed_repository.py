from sqlalchemy import select

from app.onboarding.models import Location
from app.shared.Infrastructure.db.base_repository import BaseRepository
from app.suggestions.models import Supplier


class SeedRepository(BaseRepository):
    def location_exists(self, name: str) -> bool:
        return self.db.scalar(select(Location.id).where(Location.name == name)) is not None

    def supplier_exists(self, name: str) -> bool:
        return self.db.scalar(select(Supplier.id).where(Supplier.name == name)) is not None

    def add(self, instance: object) -> None:
        self.db.add(instance)
        self.db.flush()
