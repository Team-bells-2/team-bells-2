from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.Infrastructure.db.base import Base

# Synthetic demo data only (FR-S29). Reviews are seeded; the app cannot write them (PRD section 14).


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    area: Mapped[str] = mapped_column(String(120))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class SupplierOffer(Base):
    __tablename__ = "supplier_offers"
    __table_args__ = (
        CheckConstraint("quality_grade IN ('A', 'B', 'C')", name="quality_grade"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_id: Mapped[int] = mapped_column(
        ForeignKey("suppliers.id", ondelete="CASCADE"), index=True
    )
    item: Mapped[str] = mapped_column(String(100), index=True)
    unit: Mapped[str] = mapped_column(String(40))
    unit_price_ngn: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    quantity_available: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    quality_grade: Mapped[str] = mapped_column(String(1))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SupplierReview(Base):
    __tablename__ = "supplier_reviews"
    __table_args__ = (CheckConstraint("rating BETWEEN 1 AND 5", name="rating"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_id: Mapped[int] = mapped_column(
        ForeignKey("suppliers.id", ondelete="CASCADE"), index=True
    )
    rating: Mapped[int]
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
