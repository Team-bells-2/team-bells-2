from decimal import Decimal

from app.customers.repositories.customer_repository import CustomerRepository
from app.customers.schemas import CustomerOut
from app.ledger.repositories.entry_repository import EntryRepository


class CustomerOrchestrator:
    def __init__(self, customer_repository: CustomerRepository, entry_repository: EntryRepository):
        self.customer_repository = customer_repository
        self.entry_repository = entry_repository

    def list_trader_customers(self, trader_id: int) -> list[CustomerOut]:
        balances = self.entry_repository.customer_balances(trader_id)
        return [
            CustomerOut(
                id=customer.id,
                canonical_name=customer.canonical_name,
                created_at=customer.created_at,
                balance_ngn=balances.get(customer.id, Decimal(0)),
            )
            for customer in self.customer_repository.list_customers(trader_id)
        ]
