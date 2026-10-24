from fastapi import Depends
from sqlalchemy.orm import Session

from app.inventory.repositories.inventory_repository import InventoryRepository
from app.shared.Infrastructure.db.session import get_db

# Repository factories only, so other slices can reuse them without importing routers.


def get_inventory_repository(db: Session = Depends(get_db)) -> InventoryRepository:
    return InventoryRepository(db)
