from datetime import datetime
from decimal import Decimal

from app.customers.repositories.customer_repository import CustomerRepository
from app.customers.schemas import CustomerOut
from app.ledger.repositories.entry_repository import EntryRepository
from app.shared.periods import LAGOS


class CustomerOrchestrator:
    def __init__(self, customer_repository: CustomerRepository, entry_repository: EntryRepository):
        self.customer_repository = customer_repository
        self.entry_repository = entry_repository

    def list_trader_customers(self, trader_id: int) -> list[CustomerOut]:
        balances = self.entry_repository.customer_balances(trader_id)
        past_due = self.entry_repository.customers_with_past_due_credit(trader_id, datetime.now(LAGOS).date())
        aliases: dict[int, list[str]] = {}
        for alias, customer in self.customer_repository.list_aliases(trader_id):
            if alias.casefold() != customer.canonical_name.casefold():
                aliases.setdefault(customer.id, []).append(alias)
        return [
            CustomerOut(
                id=customer.id,
                canonical_name=customer.canonical_name,
                aliases=aliases.get(customer.id, []),
                created_at=customer.created_at,
                balance_ngn=balances.get(customer.id, Decimal(0)),
                overdue=customer.id in past_due and balances.get(customer.id, Decimal(0)) > 0,
            )
            for customer in self.customer_repository.list_customers(trader_id)
        ]
