from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy import Row, func, select

from app.shared.Infrastructure.db.base_repository import BaseRepository
from app.suggestions.models import Supplier, SupplierOffer, SupplierReview


class SupplierRepository(BaseRepository):
    def list_offers_for_item(
        self, item: str
    ) -> Sequence[Row[tuple[SupplierOffer, Supplier, Decimal | None, int | None]]]:
        """Every offer for the item with its supplier and review summary, in one query."""
        ratings = (
            select(
                SupplierReview.supplier_id,
                func.avg(SupplierReview.rating).label("average_rating"),
                func.count(SupplierReview.id).label("review_count"),
            )
            .group_by(SupplierReview.supplier_id)
            .subquery()
        )
        return self.db.execute(
            select(SupplierOffer, Supplier, ratings.c.average_rating, ratings.c.review_count)
            .join(Supplier, Supplier.id == SupplierOffer.supplier_id)
            .outerjoin(ratings, ratings.c.supplier_id == Supplier.id)
            .where(func.lower(SupplierOffer.item) == item.strip().lower())
        ).all()
