from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.onboarding.models import SessionToken, Trader
from app.shared.Infrastructure.db.session import get_db
from app.shared.env import settings

bearer_scheme = HTTPBearer(auto_error=False)

# scrypt work factors: about 50 ms per check, slow enough to make guessing a PIN offline expensive.
_SCRYPT = {"n": 2**14, "r": 8, "p": 1, "dklen": 32}


def hash_pin(pin: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(pin.encode("utf-8"), salt=salt, **_SCRYPT)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_pin(pin: str, stored: str | None) -> bool:
    if not stored or not stored.startswith("scrypt$"):
        return False
    _, salt_hex, digest_hex = stored.split("$")
    digest = hashlib.scrypt(pin.encode("utf-8"), salt=bytes.fromhex(salt_hex), **_SCRYPT)
    return hmac.compare_digest(digest.hex(), digest_hex)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_session_token(db: Session, trader: Trader) -> str:
    token = secrets.token_urlsafe(32)
    db.add(
        SessionToken(
            trader_id=trader.id,
            token_hash=_token_hash(token),
            expires_at=datetime.now(UTC) + timedelta(days=settings.SESSION_TOKEN_TTL_DAYS),
        )
    )
    db.flush()
    return token


def session_for_token(db: Session, token: str | None) -> SessionToken | None:
    if not token:
        return None
    return db.scalar(
        select(SessionToken).where(
            SessionToken.token_hash == _token_hash(token),
            SessionToken.revoked_at.is_(None),
            SessionToken.expires_at > datetime.now(UTC),
        )
    )


def trader_for_token(db: Session, token: str | None) -> Trader | None:
    session_token = session_for_token(db, token)
    return db.get(Trader, session_token.trader_id) if session_token else None


def get_current_session(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> SessionToken:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail={"error": {"code": "unauthorized", "message": "Bearer session token required."}})
    session_token = session_for_token(db, credentials.credentials)
    if session_token is None:
        raise HTTPException(status_code=401, detail={"error": {"code": "invalid_session", "message": "Session token is invalid or expired."}})
    return session_token


def get_current_trader(session_token: SessionToken = Depends(get_current_session), db: Session = Depends(get_db)) -> Trader:
    trader = db.get(Trader, session_token.trader_id)
    if trader is None:
        raise HTTPException(status_code=401, detail={"error": {"code": "invalid_session", "message": "Session owner no longer exists."}})
    return trader
