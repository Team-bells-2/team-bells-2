from datetime import UTC, datetime
from decimal import Decimal

from app.customers.repositories.customer_repository import CustomerRepository
from app.demo import services
from app.demo.repositories.seed_repository import SeedRepository
from app.demo.schemas import DemoSeedResult, ResetResult, SeedSummary
from app.inventory.models import InventoryItem, StockMovement
from app.inventory.repositories.inventory_repository import InventoryRepository
from app.onboarding import services as onboarding_services
from app.onboarding.models import Location, Trader
from app.onboarding.repositories.location_repository import LocationRepository
from app.onboarding.repositories.session_repository import SessionRepository
from app.onboarding.repositories.trader_repository import TraderRepository
from app.suggestions.models import Supplier, SupplierOffer, SupplierReview


class DemoOrchestrator:
    """Reference data, and the demo reset/seed controls (FR-C10, BR-D1). Each method is one transaction."""

    def __init__(
        self,
        seed_repository: SeedRepository,
        location_repository: LocationRepository,
        trader_repository: TraderRepository,
        session_repository: SessionRepository,
        inventory_repository: InventoryRepository,
        customer_repository: CustomerRepository,
        session_ttl_days: int,
    ):
        self.seed_repository = seed_repository
        self.location_repository = location_repository
        self.trader_repository = trader_repository
        self.session_repository = session_repository
        self.inventory_repository = inventory_repository
        self.customer_repository = customer_repository
        self.session_ttl_days = session_ttl_days

    def seed_reference_data(self) -> SeedSummary:
        """Add the locations list and synthetic supplier data. Idempotent: existing names are skipped."""
        try:
            summary = self._seed_reference_data()
            self.seed_repository.commit()
        except Exception:
            self.seed_repository.rollback()
            raise
        return summary

    def reset(self) -> ResetResult:
        """No trader accounts left; locations and supplier data loaded (FR-C10)."""
        try:
            self.seed_repository.delete_trader_data()
            summary = self._seed_reference_data()
            self.seed_repository.commit()
        except Exception:
            self.seed_repository.rollback()
            raise
        return ResetResult(reference_data=summary)

    def seed_demo(self) -> DemoSeedResult:
        """The demo trader with starting stock and customers with nicknames, plus a fresh session token.
        Safe to run twice: an existing demo trader just gets a new token."""
        try:
            self._seed_reference_data()
            trader = self.trader_repository.get_trader_by_phone(services.DEMO_TRADER["phone"])
            if trader is None:
                trader = self._create_demo_trader()
            token = onboarding_services.generate_session_token()
            self.session_repository.create_session(
                trader.id,
                onboarding_services.hash_token(token),
                onboarding_services.session_expiry(datetime.now(UTC), self.session_ttl_days),
            )
            self.seed_repository.commit()
        except Exception:
            self.seed_repository.rollback()
            raise
        return DemoSeedResult(trader_id=trader.id, phone=trader.phone, pin=services.DEMO_PIN, token=token)

    def _create_demo_trader(self) -> Trader:
        location = self.location_repository.get_location_by_name(services.DEMO_TRADER["location_name"])
        assert location is not None  # seeded by _seed_reference_data
        trader = self.trader_repository.create_trader(
            Trader(
                **services.DEMO_TRADER,
                latitude=location.latitude,
                longitude=location.longitude,
                pin_hash=onboarding_services.hash_pin(services.DEMO_PIN),
            )
        )
        for name, unit, cost, opening, reorder_level, reorder_quantity in services.DEMO_ITEMS:
            item = self.inventory_repository.create_item(
                InventoryItem(
                    trader_id=trader.id,
                    name=name,
                    unit=unit,
                    unit_cost_ngn=Decimal(cost),
                    reorder_level=Decimal(reorder_level),
                    reorder_quantity=Decimal(reorder_quantity),
                )
            )
            self.inventory_repository.add_movement(
                StockMovement(inventory_item_id=item.id, quantity_change=Decimal(opening), reason="opening")
            )
        for name, aliases in services.DEMO_CUSTOMERS.items():
            customer = self.customer_repository.create_customer(trader.id, name)
            for alias in [name, *aliases]:  # the canonical name is an alias too (BR-L7)
                self.customer_repository.add_alias(customer.id, alias)
        return trader

    def _seed_reference_data(self) -> SeedSummary:
        summary = SeedSummary(locations_added=0, suppliers_added=0, offers_added=0, reviews_added=0)
        for location in services.LOCATIONS:
            if not self.seed_repository.location_exists(location["name"]):
                self.seed_repository.add(Location(**location))
                summary.locations_added += 1

        for data in services.SUPPLIERS:
            if self.seed_repository.supplier_exists(data["name"]):
                continue
            supplier = Supplier(name=data["name"], area=data["area"], latitude=data["latitude"], longitude=data["longitude"])
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
        return summary
