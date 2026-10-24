from fastapi import APIRouter, Depends

from app.customers.dependencies import get_customer_repository
from app.customers.orchestrator import CustomerOrchestrator
from app.customers.repositories.customer_repository import CustomerRepository
from app.customers.schemas import CustomerOut
from app.ledger.dependencies import get_entry_repository
from app.ledger.repositories.entry_repository import EntryRepository
from app.onboarding.models import Trader
from app.onboarding.router import get_current_trader

router = APIRouter(tags=["customers"])


def get_customer_orchestrator(
    customer_repository: CustomerRepository = Depends(get_customer_repository),
    entry_repository: EntryRepository = Depends(get_entry_repository),
) -> CustomerOrchestrator:
    return CustomerOrchestrator(customer_repository, entry_repository)


@router.get("/customers", response_model=list[CustomerOut])
def list_customers(
    trader: Trader = Depends(get_current_trader),
    orchestrator: CustomerOrchestrator = Depends(get_customer_orchestrator),
) -> list[CustomerOut]:
    return orchestrator.list_trader_customers(trader.id)
