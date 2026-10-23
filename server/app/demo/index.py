"""Seed reference data: `cd server && python -m app.demo.index` (tables must already exist)."""

from app.demo.orchestrator import DemoOrchestrator
from app.demo.repositories.seed_repository import SeedRepository
from app.shared.Infrastructure.db.session import SessionLocal


def main() -> None:
    with SessionLocal() as db:
        summary = DemoOrchestrator(SeedRepository(db)).seed_reference_data()
    print(summary.model_dump_json())


if __name__ == "__main__":
    main()
