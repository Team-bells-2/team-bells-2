from app.demo import services
from app.demo.repositories.seed_repository import SeedRepository
from app.demo.schemas import SeedSummary
from app.onboarding.models import Location
from app.suggestions.models import Supplier, SupplierOffer, SupplierReview


class DemoOrchestrator:
    def __init__(self, seed_repository: SeedRepository):
        self.seed_repository = seed_repository

    def seed_reference_data(self) -> SeedSummary:
        """Add the locations list and synthetic supplier data. Idempotent: existing names are skipped."""
        summary = SeedSummary(locations_added=0, suppliers_added=0, offers_added=0, reviews_added=0)
        try:
            for location in services.LOCATIONS:
                if not self.seed_repository.location_exists(location["name"]):
                    self.seed_repository.add(Location(**location))
                    summary.locations_added += 1

            for data in services.SUPPLIERS:
                if self.seed_repository.supplier_exists(data["name"]):
                    continue
                supplier = Supplier(
                    name=data["name"], area=data["area"], latitude=data["latitude"], longitude=data["longitude"]
                )
                self.seed_repository.add(supplier)
                summary.suppliers_added += 1
                for item, unit, price, quantity, grade in data["offers"]:
                    self.seed_repository.add(
                        SupplierOffer(
                            supplier_id=supplier.id,
                            item=item,
                            unit=unit,
                            unit_price_ngn=services.as_decimal(price),
                            quantity_available=services.as_decimal(quantity),
                            quality_grade=grade,
                        )
                    )
                    summary.offers_added += 1
                for rating, comment in data["reviews"]:
                    self.seed_repository.add(SupplierReview(supplier_id=supplier.id, rating=rating, comment=comment))
                    summary.reviews_added += 1
            self.seed_repository.commit()
        except Exception:
            self.seed_repository.rollback()
            raise
        return summary
