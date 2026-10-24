from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy import Row, func, select

from app.shared.Infrastructure.db.base_repository import BaseRepository
from app.shared.matching import match_key
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
        rows = self.db.execute(
            select(SupplierOffer, Supplier, ratings.c.average_rating, ratings.c.review_count)
            .join(Supplier, Supplier.id == SupplierOffer.supplier_id)
            .outerjoin(ratings, ratings.c.supplier_id == Supplier.id)
        ).all()
        # Item names are matched with match_key ("rices" = "rice"); the demo offer list is small.
        key = match_key(item)
        return [row for row in rows if match_key(row[0].item) == key]
