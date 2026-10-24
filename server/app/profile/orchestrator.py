from app.onboarding.models import Trader
from app.onboarding.repositories.location_repository import LocationRepository
from app.onboarding.repositories.trader_repository import TraderRepository
from app.profile import services
from app.profile.schemas import ProfileOut, ProfileUpdate
from app.shared.errors import AppError
from app.shared.Infrastructure.realtime.hub import EventPublisher


class ProfileOrchestrator:
    def __init__(
        self, location_repository: LocationRepository, trader_repository: TraderRepository, events: EventPublisher
    ):
        self.location_repository = location_repository
        self.trader_repository = trader_repository
        self.events = events

    def update_profile(self, trader: Trader, update: ProfileUpdate) -> Trader:
        location = None
        if update.location_name is not None:
            location = self.location_repository.get_location_by_name(update.location_name)
            if location is None:
                raise AppError(422, "unknown_location", f"'{update.location_name}' is not a supported market or area.")

        try:
            services.apply_profile_update(trader, update, location)
            self.trader_repository.commit()
        except Exception:
            self.trader_repository.rollback()
            raise
        self.trader_repository.refresh(trader)
        self.events.publish(trader.id, "profile_updated", ProfileOut.model_validate(trader))
        return trader
