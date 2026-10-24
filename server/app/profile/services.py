from app.onboarding.models import Location, Trader
from app.profile.schemas import ProfileUpdate


def apply_profile_update(trader: Trader, update: ProfileUpdate, location: Location | None) -> Trader:
    if update.name is not None:
        trader.name = update.name
    if update.business_name is not None:
        trader.business_name = update.business_name
    if update.sector is not None:
        trader.sector = update.sector
    if location is not None:
        trader.location_name = location.name
        trader.latitude = location.latitude
        trader.longitude = location.longitude
    return trader
