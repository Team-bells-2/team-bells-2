"""Seed reference data: `cd server && python -m app.demo.index` (tables must already exist)."""

from app.customers.repositories.customer_repository import CustomerRepository
from app.demo.orchestrator import DemoOrchestrator
from app.demo.repositories.seed_repository import SeedRepository
from app.inventory.repositories.inventory_repository import InventoryRepository
from app.onboarding.repositories.location_repository import LocationRepository
from app.onboarding.repositories.session_repository import SessionRepository
from app.onboarding.repositories.trader_repository import TraderRepository
from app.shared.env import settings
from app.shared.Infrastructure.db.session import SessionLocal


def main() -> None:
    with SessionLocal() as db:
        orchestrator = DemoOrchestrator(
            SeedRepository(db),
            LocationRepository(db),
            TraderRepository(db),
            SessionRepository(db),
            InventoryRepository(db),
            CustomerRepository(db),
            settings.SESSION_TOKEN_TTL_DAYS,
        )
        summary = orchestrator.seed_reference_data()
    print(summary.model_dump_json())


if __name__ == "__main__":
    main()
