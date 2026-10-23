from sqlalchemy import func, select

from app.onboarding.models import Location
from app.shared.Infrastructure.db.base_repository import BaseRepository


class LocationRepository(BaseRepository):
    def get_location_by_name(self, name: str) -> Location | None:
        return self.db.scalar(select(Location).where(func.lower(Location.name) == name.lower()))
