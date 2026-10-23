from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.Infrastructure.db.base import Base

MOVEMENT_REASONS = ("opening", "restock", "sale", "adjustment")


class InventoryItem(Base):
    """Item details only. Quantity on hand is never stored; it is the sum of stock movements (FR-S24)."""

    __tablename__ = "inventory_items"
    __table_args__ = (UniqueConstraint("trader_id", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    trader_id: Mapped[int] = mapped_column(ForeignKey("traders.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    unit: Mapped[str] = mapped_column(String(40))
    unit_cost_ngn: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    reorder_level: Mapped[Decimal] = mapped_column(Numeric(14, 3), server_default="0")
    reorder_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class StockMovement(Base):
    __tablename__ = "stock_movements"
    __table_args__ = (
        CheckConstraint(f"reason IN {MOVEMENT_REASONS}", name="reason"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    inventory_item_id: Mapped[int] = mapped_column(ForeignKey("inventory_items.id", ondelete="CASCADE"), index=True)
    entry_id: Mapped[int | None] = mapped_column(ForeignKey("entries.id", ondelete="SET NULL"), index=True)
    quantity_change: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    reason: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
