from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.Infrastructure.db.base import Base


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (UniqueConstraint("trader_id", "canonical_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    trader_id: Mapped[int] = mapped_column(
        ForeignKey("traders.id", ondelete="CASCADE"), index=True
    )
    canonical_name: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class CustomerAlias(Base):
    """Other names a trader uses for a customer, e.g. "the rice woman" (FR-S9)."""

    __tablename__ = "customer_aliases"
    __table_args__ = (UniqueConstraint("customer_id", "alias"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), index=True
    )
    alias: Mapped[str] = mapped_column(String(120), index=True)
