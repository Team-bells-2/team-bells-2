from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Row, case, func, select

from app.customers.models import Customer
from app.ledger.models import Entry, EntryEdit
from app.shared.Infrastructure.db.base_repository import BaseRepository


class EntryRepository(BaseRepository):
    def create_entry(self, entry: Entry) -> Entry:
        self.db.add(entry)
        self.db.flush()
        return entry

    def add_edit(self, edit: EntryEdit) -> EntryEdit:
        self.db.add(edit)
        self.db.flush()
        return edit

    def get_last_saved_entry(self, trader_id: int) -> Entry | None:
        return self.db.scalar(
            select(Entry)
            .where(Entry.trader_id == trader_id, Entry.status == "saved")
            .order_by(Entry.created_at.desc(), Entry.id.desc())
            .limit(1)
        )

    def list_entries(
        self,
        trader_id: int,
        since: datetime | None,
        entry_type: str | None,
        limit: int,
        offset: int,
    ) -> Sequence[Row[tuple[Entry, str | None]]]:
        """Saved entries newest first, each with its customer's canonical name."""
        query = (
            select(Entry, Customer.canonical_name)
            .outerjoin(Customer, Customer.id == Entry.customer_id)
            .where(Entry.trader_id == trader_id, Entry.status == "saved")
        )
        if since is not None:
            query = query.where(Entry.created_at >= since)
        if entry_type is not None:
            query = query.where(Entry.type == entry_type)
        return self.db.execute(
            query.order_by(Entry.created_at.desc(), Entry.id.desc()).limit(limit).offset(offset)
        ).all()

    def period_totals(self, trader_id: int, since: datetime) -> tuple[Decimal, Decimal, int]:
        """Revenue (sale + credit_sale), expenses and number of entries since a moment (FR-S27)."""
        revenue = func.coalesce(
            func.sum(case((Entry.type.in_(("sale", "credit_sale")), Entry.amount_ngn), else_=0)), 0
        )
        expenses = func.coalesce(func.sum(case((Entry.type == "expense", Entry.amount_ngn), else_=0)), 0)
        row = self.db.execute(
            select(revenue, expenses, func.count(Entry.id)).where(
                Entry.trader_id == trader_id, Entry.status == "saved", Entry.created_at >= since
            )
        ).one()
        return Decimal(row[0]), Decimal(row[1]), int(row[2])

    def customer_balances(self, trader_id: int) -> dict[int, Decimal]:
        """Balance per customer: credit sales add, payments subtract (FR-S10). One grouped query."""
        balance = func.sum(
            case(
                (Entry.type == "credit_sale", Entry.amount_ngn),
                (Entry.type == "payment_received", -Entry.amount_ngn),
                else_=0,
            )
        )
        rows = self.db.execute(
            select(Entry.customer_id, balance)
            .where(Entry.trader_id == trader_id, Entry.status == "saved", Entry.customer_id.is_not(None))
            .group_by(Entry.customer_id)
        ).all()
        return {int(customer_id): Decimal(total or 0) for customer_id, total in rows}
