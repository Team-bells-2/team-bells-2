from fastapi import Depends
from sqlalchemy.orm import Session

from app.customers.repositories.customer_repository import CustomerRepository
from app.shared.Infrastructure.db.session import get_db

# Repository factories only, so other slices can reuse them without importing routers.


def get_customer_repository(db: Session = Depends(get_db)) -> CustomerRepository:
    return CustomerRepository(db)
