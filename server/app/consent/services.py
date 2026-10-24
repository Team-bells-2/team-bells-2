import hashlib
import secrets
from collections.abc import Iterable
from datetime import UTC, date, datetime
from decimal import Decimal

from app.shared.periods import LAGOS

# The agent summary covers the last 30 days (BR-K6).
SUMMARY_PERIOD_DAYS = 30
LOG_ROWS_SHOWN = 20


def new_secret() -> str:
    return secrets.token_urlsafe(32)


def hash_secret(secret: str) -> str:
    # Secrets are random and high-entropy, so a fast hash is enough; only the hash is stored.
    return hashlib.sha256(secret.encode()).hexdigest()


def secrets_match(stored_hash: str, secret: str) -> bool:
    return secrets.compare_digest(stored_hash, hash_secret(secret))


def as_utc(moment: datetime) -> datetime:
    """SQLite returns naive datetimes; every stored moment is UTC."""
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)


def duration_text(minutes: int) -> str:
    """ACCESS_TOKEN_TTL_MINUTES in words, for the consent prompt."""
    for size, unit in ((1440, "day"), (60, "hour")):
        if minutes >= size and minutes % size == 0:
            count = minutes // size
            return f"{count} {unit}{'s' if count != 1 else ''}"
    return f"{minutes} minute{'s' if minutes != 1 else ''}"


def consent_prompt(agent_name: str, scopes: Iterable[str], ttl_minutes: int) -> str:
    """e.g. "QuickLoan agent wants to see your sales total, total owed for 30 days. Approve?" (FR-C3)."""
    readable = ", ".join(scope.replace("_", " ") for scope in scopes)
    return f"{agent_name} wants to see your {readable} for {duration_text(ttl_minutes)}. Approve?"


def active_days(moments: Iterable[datetime]) -> int:
    """Distinct Lagos dates with at least one entry (BR-K6)."""
    days: set[date] = {as_utc(moment).astimezone(LAGOS).date() for moment in moments}
    return len(days)


def total_owed(balances: Iterable[Decimal]) -> Decimal:
    return sum((balance for balance in balances if balance > 0), Decimal(0))
