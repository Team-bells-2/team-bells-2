from __future__ import annotations

from fastapi import FastAPI

from app.ask.index import router as ask_router
from app.customers.index import router as customers_router
from app.home.index import router as home_router
from app.inventory.index import router as inventory_router
from app.ledger.index import router as ledger_router
from app.onboarding.index import router as onboarding_router
from app.shared.Infrastructure.db.session import initialize_database
from app.shared.errors import install_error_handlers

app = FastAPI(title="OJA API", version="0.1.0")
install_error_handlers(app)

app.include_router(onboarding_router)
app.include_router(ledger_router)
app.include_router(customers_router)
app.include_router(ask_router)
app.include_router(inventory_router)
app.include_router(home_router)


@app.on_event("startup")
def create_database_tables() -> None:
    initialize_database()


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
