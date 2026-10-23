from __future__ import annotations

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.Infrastructure.db.base import Base


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (UniqueConstraint("trader_id", "canonical_name", name="uq_customer_trader_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    trader_id: Mapped[int] = mapped_column(ForeignKey("traders.id", ondelete="CASCADE"), index=True)
    canonical_name: Mapped[str] = mapped_column(String(120))


class CustomerAlias(Base):
    __tablename__ = "customer_aliases"
    __table_args__ = (UniqueConstraint("customer_id", "alias", name="uq_customer_alias"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), index=True)
    alias: Mapped[str] = mapped_column(String(120), index=True)
