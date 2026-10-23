from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.ask.index import router as ask_router
from app.consent.index import router as consent_router
from app.customers.index import router as customers_router
from app.demo.index import router as demo_router
from app.home.index import router as home_router
from app.inventory.index import router as inventory_router
from app.ledger.index import router as ledger_router
from app.onboarding.index import router as onboarding_router
from app.shared.Infrastructure.db.session import initialize_database
from app.shared.env import settings
from app.shared.errors import install_error_handlers
from app.shared.realtime import manager as realtime_manager
from app.shared.realtime import router as realtime_router
from app.suggestions.index import router as suggestions_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    initialize_database()
    realtime_manager.bind_loop(asyncio.get_running_loop())
    yield


app = FastAPI(title="OJA API", version="0.1.0", lifespan=lifespan)
install_error_handlers(app)
if settings.CORS_ORIGINS:
    app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])

app.include_router(onboarding_router)
app.include_router(ledger_router)
app.include_router(customers_router)
app.include_router(ask_router)
app.include_router(inventory_router)
app.include_router(home_router)
app.include_router(suggestions_router)
app.include_router(consent_router)
app.include_router(demo_router)
app.include_router(realtime_router)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
