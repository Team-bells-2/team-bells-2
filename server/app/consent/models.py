from datetime import datetime
from typing import Any

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.Infrastructure.db.base import Base

REQUEST_STATUSES = ("pending", "approved", "rejected", "revoked")

JsonList = JSON().with_variant(JSONB(), "postgresql")


class AccessRequest(Base):
    """A lender agent asking to see a trader's totals (FR-S13)."""

    __tablename__ = "access_requests"
    __table_args__ = (CheckConstraint(f"status IN {REQUEST_STATUSES}", name="status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    trader_id: Mapped[int] = mapped_column(ForeignKey("traders.id", ondelete="CASCADE"), index=True)
    agent_name: Mapped[str] = mapped_column(String(120))
    purpose: Mapped[str] = mapped_column(Text)
    scopes: Mapped[list[Any]] = mapped_column(JsonList)
    status: Mapped[str] = mapped_column(String(20), server_default="pending", index=True)
    # Hash of the secret the agent uses to poll for the decision and collect its token once (BR-K2).
    claim_hash: Mapped[str] = mapped_column(String(64))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AccessToken(Base):
    """Issued once, when the agent collects it after approval; only the hash is stored (FR-S14)."""

    __tablename__ = "access_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("access_requests.id", ondelete="CASCADE"), unique=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AccessLog(Base):
    """Every agent access and consent decision (FR-S16). request_id is empty for unknown tokens."""

    __tablename__ = "access_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int | None] = mapped_column(ForeignKey("access_requests.id", ondelete="CASCADE"), index=True)
    endpoint: Mapped[str] = mapped_column(String(120))
    result: Mapped[str] = mapped_column(String(40))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
