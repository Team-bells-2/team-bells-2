from fastapi import Depends
from sqlalchemy.orm import Session

from app.onboarding.repositories.location_repository import LocationRepository
from app.onboarding.repositories.session_repository import SessionRepository
from app.onboarding.repositories.trader_repository import TraderRepository
from app.shared.Infrastructure.db.session import get_db

# Repository factories only, so other slices can reuse them without importing routers.


def get_location_repository(db: Session = Depends(get_db)) -> LocationRepository:
    return LocationRepository(db)


def get_trader_repository(db: Session = Depends(get_db)) -> TraderRepository:
    return TraderRepository(db)


def get_session_repository(db: Session = Depends(get_db)) -> SessionRepository:
    return SessionRepository(db)
