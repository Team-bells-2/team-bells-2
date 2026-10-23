from __future__ import annotations

import hashlib
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


def issue_session_token(db: Session, trader: Trader) -> str:
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    db.add(
        SessionToken(
            trader_id=trader.id,
            token_hash=token_hash,
            expires_at=datetime.now(UTC) + timedelta(days=settings.SESSION_TOKEN_TTL_DAYS),
        )
    )
    db.flush()
    return token


def get_current_trader(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Trader:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail={"error": {"code": "unauthorized", "message": "Bearer session token required."}})
    token_hash = hashlib.sha256(credentials.credentials.encode("utf-8")).hexdigest()
    session_token = db.scalar(
        select(SessionToken).where(
            SessionToken.token_hash == token_hash,
            SessionToken.revoked_at.is_(None),
            SessionToken.expires_at > datetime.now(UTC),
        )
    )
    if session_token is None:
        raise HTTPException(status_code=401, detail={"error": {"code": "invalid_session", "message": "Session token is invalid or expired."}})
    trader = db.get(Trader, session_token.trader_id)
    if trader is None:
        raise HTTPException(status_code=401, detail={"error": {"code": "invalid_session", "message": "Session owner no longer exists."}})
    return trader
