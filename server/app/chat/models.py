from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.Infrastructure.db.base import Base

CHAT_ROLES = ("trader", "assistant")


class ChatMessage(Base):
    """One side of an assistant turn, kept so the app can restore the chat (one chat per trader).

    Turns from POST /messages carry the app's client_message_id; the unique constraint keeps a
    retried message from being stored twice. Turns from POST /ask have none.
    """

    __tablename__ = "chat_messages"
    __table_args__ = (
        CheckConstraint(f"role IN {CHAT_ROLES}", name="role"),
        UniqueConstraint("trader_id", "client_message_id", "role", name="uq_chat_messages_trader_client_role"),
        Index("ix_chat_messages_trader_id_id", "trader_id", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    trader_id: Mapped[int] = mapped_column(ForeignKey("traders.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(10))
    text: Mapped[str] = mapped_column(Text)
    # The entry this reply saved or corrected, so the app can open it in the ledger.
    entry_id: Mapped[int | None] = mapped_column(ForeignKey("entries.id", ondelete="SET NULL"))
    client_message_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
