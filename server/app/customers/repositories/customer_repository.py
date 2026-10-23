from collections.abc import Sequence

from sqlalchemy import func, select
from app.customers.models import Customer, CustomerAlias
from app.shared.Infrastructure.db.base_repository import BaseRepository


class CustomerRepository(BaseRepository):
    def list_customers(self, trader_id: int) -> Sequence[Customer]:
        return self.db.scalars(
            select(Customer)
            .where(Customer.trader_id == trader_id)
            .order_by(Customer.canonical_name)
        ).all()

    def get_customer_by_id(self, trader_id: int, customer_id: int) -> Customer | None:
        return self.db.scalar(
            select(Customer).where(Customer.trader_id == trader_id, Customer.id == customer_id)
        )

    def get_customer_by_name(self, trader_id: int, name: str) -> Customer | None:
        return self.db.scalar(
            select(Customer).where(
                Customer.trader_id == trader_id,
                func.lower(Customer.canonical_name) == name.strip().lower(),
            )
        )

    def find_customers_by_alias(self, trader_id: int, alias: str) -> Sequence[Customer]:
        """All of the trader's customers with this alias; more than one means the name is ambiguous."""
        return self.db.scalars(
            select(Customer)
            .join(CustomerAlias, CustomerAlias.customer_id == Customer.id)
            .where(
                Customer.trader_id == trader_id,
                func.lower(CustomerAlias.alias) == alias.strip().lower(),
            )
            .distinct()
        ).all()

    def create_customer(self, trader_id: int, canonical_name: str) -> Customer:
        customer = Customer(trader_id=trader_id, canonical_name=canonical_name.strip())
        self.db.add(customer)
        self.db.flush()
        return customer

    def add_alias(self, customer_id: int, alias: str) -> CustomerAlias:
        customer_alias = CustomerAlias(customer_id=customer_id, alias=alias.strip())
        self.db.add(customer_alias)
        self.db.flush()
        return customer_alias
