from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.Infrastructure.db.base import Base

ENTRY_TYPES = ("sale", "credit_sale", "payment_received", "expense")
ENTRY_STATUSES = ("pending", "saved")

JsonDict = JSON().with_variant(JSONB(), "postgresql")


class Entry(Base):
    __tablename__ = "entries"
    __table_args__ = (
        CheckConstraint(f"type IN {ENTRY_TYPES}", name="type"),
        CheckConstraint(f"status IN {ENTRY_STATUSES}", name="status"),
        Index("ix_entries_trader_id_created_at", "trader_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    trader_id: Mapped[int] = mapped_column(
        ForeignKey("traders.id", ondelete="CASCADE"), index=True
    )
    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customers.id", ondelete="SET NULL"), index=True
    )
    inventory_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="SET NULL"), index=True
    )
    type: Mapped[str] = mapped_column(String(20))
    item: Mapped[str | None] = mapped_column(String(100))
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    unit: Mapped[str | None] = mapped_column(String(40))
    amount_ngn: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    due_date: Mapped[date | None] = mapped_column(Date)
    confidence: Mapped[float | None] = mapped_column(Float)
    raw_text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10), server_default="saved")
    # FR-S25: "not_in_inventory" or "check_stock" when the entry could not move stock as recorded.
    stock_warning: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class EntryEdit(Base):
    """Audit trail for corrections (FR-S6)."""

    __tablename__ = "entry_edits"

    id: Mapped[int] = mapped_column(primary_key=True)
    entry_id: Mapped[int] = mapped_column(
        ForeignKey("entries.id", ondelete="CASCADE"), index=True
    )
    old_values: Mapped[dict[str, Any]] = mapped_column(JsonDict)
    new_values: Mapped[dict[str, Any]] = mapped_column(JsonDict)
    edited_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ProcessedMessage(Base):
    """Idempotency record per app message (NFR-5). `response` is the original reply,
    replayed when the app retries the same client_message_id."""

    __tablename__ = "processed_messages"

    trader_id: Mapped[int] = mapped_column(
        ForeignKey("traders.id", ondelete="CASCADE"), primary_key=True
    )
    client_message_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    response: Mapped[dict[str, Any]] = mapped_column(JsonDict)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class PendingClarification(Base):
    """The one entry a trader is still completing (FR-S5); at most one per trader."""

    __tablename__ = "pending_clarifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    trader_id: Mapped[int] = mapped_column(
        ForeignKey("traders.id", ondelete="CASCADE"), unique=True
    )
    partial_entry: Mapped[dict[str, Any]] = mapped_column(JsonDict)
    question: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
