import hashlib
import secrets

from app.onboarding.models import Location, Trader
from app.onboarding.schemas import OnboardingRequest


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    # Tokens are random and high-entropy, so a fast hash is enough; only the hash is stored.
    return hashlib.sha256(token.encode()).hexdigest()


def build_trader(request: OnboardingRequest, location: Location) -> Trader:
    return Trader(
        name=request.name,
        phone=request.phone,
        business_name=request.business_name,
        sector=request.sector,
        location_name=location.name,
        latitude=location.latitude,
        longitude=location.longitude,
    )
