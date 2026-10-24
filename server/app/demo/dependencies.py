from fastapi import Depends
from sqlalchemy.orm import Session

from app.demo.repositories.seed_repository import SeedRepository
from app.shared.Infrastructure.db.session import get_db

# Repository factories only, so other slices can reuse them without importing routers.


def get_seed_repository(db: Session = Depends(get_db)) -> SeedRepository:
    return SeedRepository(db)
