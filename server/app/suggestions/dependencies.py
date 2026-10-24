from fastapi import Depends
from sqlalchemy.orm import Session

from app.shared.Infrastructure.db.session import get_db
from app.suggestions.repositories.supplier_repository import SupplierRepository

# Repository factories only, so other slices can reuse them without importing routers.


def get_supplier_repository(db: Session = Depends(get_db)) -> SupplierRepository:
    return SupplierRepository(db)
