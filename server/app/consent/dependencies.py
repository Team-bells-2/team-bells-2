from fastapi import Depends
from sqlalchemy.orm import Session

from app.consent.repositories.access_repository import AccessRepository
from app.shared.Infrastructure.db.session import get_db

# Repository factories only, so other slices can reuse them without importing routers.


def get_access_repository(db: Session = Depends(get_db)) -> AccessRepository:
    return AccessRepository(db)
