from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.ask.router import router as ask_router
from app.consent.router import router as consent_router
from app.customers.router import router as customers_router
from app.demo.router import router as demo_router
from app.home.router import router as home_router
from app.inventory.router import router as inventory_router
from app.ledger.router import router as ledger_router
from app.onboarding.router import router as onboarding_router
from app.profile.router import router as profile_router
from app.shared.env import settings
from app.shared.errors import register_error_handlers
from app.suggestions.router import router as suggestions_router

app = FastAPI(title="OJA API")
register_error_handlers(app)
# Browser calls only from the origins in CORS_ORIGINS (NFR-7). Auth is a bearer header, so no cookies.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Claim-Secret"],
)

app.include_router(onboarding_router)
app.include_router(profile_router)
app.include_router(customers_router)
app.include_router(ledger_router)
app.include_router(inventory_router)
app.include_router(home_router)
app.include_router(suggestions_router)
app.include_router(ask_router)
app.include_router(consent_router)
app.include_router(demo_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
