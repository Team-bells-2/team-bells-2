import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

from app.onboarding.models import Location, Trader
from app.onboarding.schemas import OnboardingRequest
from app.shared.periods import as_utc

# scrypt work factors: about 50 ms per check, so guessing a PIN offline is expensive (BR-O3).
_SCRYPT = {"n": 2**14, "r": 8, "p": 1, "dklen": 32}


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    # Tokens are random and high-entropy, so a fast hash is enough; only the hash is stored.
    return hashlib.sha256(token.encode()).hexdigest()


def session_expiry(now: datetime, ttl_days: int) -> datetime:
    return now + timedelta(days=ttl_days)


def effective_expiry(expires_at: datetime | None, created_at: datetime, ttl_days: int) -> datetime:
    """A session created before expiry existed expires TTL days after it was created (BR-O4).
    Computed on read, so checking a token never writes to the database."""
    return as_utc(expires_at) if expires_at is not None else session_expiry(as_utc(created_at), ttl_days)


def hash_pin(pin: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(pin.encode(), salt=salt, **_SCRYPT)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_pin(pin: str, stored: str | None) -> bool:
    if not stored or not stored.startswith("scrypt$"):
        return False
    _, salt_hex, digest_hex = stored.split("$")
    digest = hashlib.scrypt(pin.encode(), salt=bytes.fromhex(salt_hex), **_SCRYPT)
    return hmac.compare_digest(digest.hex(), digest_hex)


# Checked when the phone is unknown or has no PIN, so every failed login takes the same time (BR-O3).
DUMMY_PIN_HASH = hash_pin("000000")


def lock_message(minutes_left: int) -> str:
    return f"Too many wrong PINs. Try again in {minutes_left} minute{'s' if minutes_left != 1 else ''}."


def build_trader(request: OnboardingRequest, location: Location) -> Trader:
    return Trader(
        name=request.name,
        phone=request.phone,
        business_name=request.business_name,
        sector=request.sector,
        location_name=location.name,
        latitude=location.latitude,
        longitude=location.longitude,
        pin_hash=hash_pin(request.pin) if request.pin else None,
    )
