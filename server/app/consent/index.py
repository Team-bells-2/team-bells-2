from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.consent.models import AccessLog, AccessRequest, AccessToken
from app.customers.index import customer_balances
from app.ledger.models import Entry
from app.onboarding.models import Trader
from app.shared.Infrastructure.db.session import get_db
from app.shared.auth import get_current_trader
from app.shared.env import settings

router = APIRouter(tags=["consent"])
agent_bearer = HTTPBearer(auto_error=False)

SCOPES = ("sales_total", "active_days", "total_owed")
SUMMARY_PERIOD_DAYS = 30


def _hash(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def _aware(moment: datetime | None) -> datetime | None:
    # SQLite returns naive datetimes; everything is stored in UTC.
    return moment.replace(tzinfo=UTC) if moment is not None and moment.tzinfo is None else moment


def _error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"error": {"code": code, "message": message}})


class AccessRequestCreate(BaseModel):
    trader_phone: str = Field(min_length=7, max_length=32)
    agent_name: str = Field(min_length=1, max_length=120)
    purpose: str = Field(min_length=3, max_length=500)
    data_scopes: list[Literal["sales_total", "active_days", "total_owed"]] = Field(min_length=1)

    @field_validator("data_scopes")
    @classmethod
    def unique_scopes(cls, scopes: list[str]) -> list[str]:
        return list(dict.fromkeys(scopes))


class Decision(BaseModel):
    approve: bool


class AgentSummary(BaseModel):
    """Allow-list response (FR-S15): totals only, never names, raw text, entry IDs or profile data."""

    period_days: int
    generated_at: datetime
    scopes: list[str]
    sales_total_ngn: int | None = None
    active_days: int | None = None
    total_owed_ngn: int | None = None


@router.post("/access-requests", status_code=202)
def create_access_request(payload: AccessRequestCreate, db: Session = Depends(get_db)) -> dict:
    """Open endpoint for agents. Returns no business data, only a secret to poll for the decision."""
    trader = db.scalar(select(Trader).where(Trader.phone == payload.trader_phone.strip()))
    if trader is None:
        raise _error(404, "trader_not_found", "No trader uses that phone number.")
    claim_secret = secrets.token_urlsafe(24)
    request = AccessRequest(
        trader_id=trader.id, agent_name=payload.agent_name.strip(), purpose=payload.purpose.strip(),
        scopes=payload.data_scopes, claim_hash=_hash(claim_secret),
    )
    db.add(request)
    db.flush()
    db.add(AccessLog(request_id=request.id, endpoint="POST /access-requests", result="requested"))
    db.commit()
    return {"request_id": request.id, "status": "pending", "claim_secret": claim_secret}


@router.get("/access-requests/{request_id}/status")
def access_request_status(request_id: int, x_claim_secret: str = Header(min_length=8), db: Session = Depends(get_db)) -> dict:
    """The agent polls here. After approval the token is returned exactly once."""
    request = db.get(AccessRequest, request_id)
    if request is None or not secrets.compare_digest(request.claim_hash, _hash(x_claim_secret)):
        raise _error(404, "request_not_found", "Access request not found.")
    response = {"request_id": request.id, "status": request.status, "scopes": request.scopes}
    if request.status == "approved":
        issued = db.scalar(select(AccessToken).where(AccessToken.request_id == request.id))
        if issued is None:
            token = secrets.token_urlsafe(32)
            db.add(AccessToken(request_id=request.id, token_hash=_hash(token), expires_at=request.expires_at))
            db.add(AccessLog(request_id=request.id, endpoint="GET /access-requests/{id}/status", result="token_issued"))
            db.commit()
            response.update({"access_token": token, "token_type": "bearer", "expires_at": _aware(request.expires_at)})
        else:
            response.update({"token_already_collected": True, "expires_at": _aware(issued.expires_at)})
    return response


@router.get("/access-requests")
def list_access_requests(
    status: Literal["pending", "approved", "rejected", "revoked"] | None = Query(default=None),
    trader: Trader = Depends(get_current_trader),
    db: Session = Depends(get_db),
) -> list[dict]:
    query = select(AccessRequest).where(AccessRequest.trader_id == trader.id)
    if status:
        query = query.where(AccessRequest.status == status)
    requests = db.scalars(query.order_by(AccessRequest.requested_at.desc(), AccessRequest.id.desc())).all()
    result = []
    for request in requests:
        log = db.scalars(select(AccessLog).where(AccessLog.request_id == request.id).order_by(AccessLog.at.desc(), AccessLog.id.desc()).limit(20)).all()
        result.append({
            "id": request.id, "agent_name": request.agent_name, "purpose": request.purpose, "scopes": request.scopes,
            "status": request.status, "requested_at": _aware(request.requested_at), "decided_at": _aware(request.decided_at),
            "expires_at": _aware(request.expires_at),
            "prompt": f"{request.agent_name} wants to see your {', '.join(scope.replace('_', ' ') for scope in request.scopes)} for {SUMMARY_PERIOD_DAYS} days. Approve?",
            "log": [{"endpoint": row.endpoint, "result": row.result, "at": _aware(row.at)} for row in log],
        })
    return result


@router.post("/access-requests/{request_id}/approve")
def decide_access_request(request_id: int, payload: Decision, trader: Trader = Depends(get_current_trader), db: Session = Depends(get_db)) -> dict:
    request = db.scalar(select(AccessRequest).where(AccessRequest.id == request_id, AccessRequest.trader_id == trader.id))
    if request is None:
        raise _error(404, "request_not_found", "Access request not found.")
    if request.status != "pending":
        raise _error(409, "already_decided", f"This request is already {request.status}.")
    now = datetime.now(UTC)
    request.status = "approved" if payload.approve else "rejected"
    request.decided_at = now
    if payload.approve:
        request.expires_at = now + timedelta(minutes=settings.ACCESS_TOKEN_TTL_MINUTES)
    db.add(AccessLog(request_id=request.id, endpoint="POST /access-requests/{id}/approve", result=request.status))
    db.commit()
    return {"id": request.id, "status": request.status, "expires_at": _aware(request.expires_at)}


@router.delete("/access/{request_id}")
def revoke_access(request_id: int, trader: Trader = Depends(get_current_trader), db: Session = Depends(get_db)) -> dict:
    request = db.scalar(select(AccessRequest).where(AccessRequest.id == request_id, AccessRequest.trader_id == trader.id))
    if request is None:
        raise _error(404, "request_not_found", "Access request not found.")
    now = datetime.now(UTC)
    request.status = "revoked"
    token = db.scalar(select(AccessToken).where(AccessToken.request_id == request.id))
    if token and token.revoked_at is None:
        token.revoked_at = now
    db.add(AccessLog(request_id=request.id, endpoint="DELETE /access/{id}", result="revoked"))
    db.commit()
    return {"id": request.id, "status": "revoked"}


@router.get("/agent/summary", response_model=AgentSummary, response_model_exclude_none=True)
def agent_summary(credentials: HTTPAuthorizationCredentials | None = Depends(agent_bearer), db: Session = Depends(get_db)) -> AgentSummary:
    endpoint = "GET /agent/summary"
    if credentials is None:
        db.add(AccessLog(request_id=None, endpoint=endpoint, result="missing_token"))
        db.commit()
        raise _error(401, "missing_token", "Bearer access token required.")
    token = db.scalar(select(AccessToken).where(AccessToken.token_hash == _hash(credentials.credentials)))
    if token is None:
        db.add(AccessLog(request_id=None, endpoint=endpoint, result="invalid_token"))
        db.commit()
        raise _error(401, "invalid_token", "Access token is not valid.")
    request = db.get(AccessRequest, token.request_id)
    now = datetime.now(UTC)
    if token.revoked_at is not None or request.status == "revoked":
        db.add(AccessLog(request_id=request.id, endpoint=endpoint, result="revoked"))
        db.commit()
        raise _error(403, "revoked", "The trader revoked this access.")
    if _aware(token.expires_at) <= now:
        db.add(AccessLog(request_id=request.id, endpoint=endpoint, result="expired"))
        db.commit()
        raise _error(401, "expired", "This access token has expired.")

    since = now - timedelta(days=SUMMARY_PERIOD_DAYS)
    summary = AgentSummary(period_days=SUMMARY_PERIOD_DAYS, generated_at=now, scopes=request.scopes)
    if "sales_total" in request.scopes:
        summary.sales_total_ngn = int(db.scalar(select(func.coalesce(func.sum(Entry.amount_ngn), 0)).where(
            Entry.trader_id == request.trader_id, Entry.type.in_(["sale", "credit_sale"]), Entry.created_at >= since,
        )) or 0)
    if "active_days" in request.scopes:
        moments = db.scalars(select(Entry.created_at).where(Entry.trader_id == request.trader_id, Entry.created_at >= since)).all()
        summary.active_days = len({_aware(moment).date() for moment in moments})
    if "total_owed" in request.scopes:
        summary.total_owed_ngn = sum(balance for _, balance, _ in customer_balances(db, request.trader_id) if balance > 0)
    db.add(AccessLog(request_id=request.id, endpoint=endpoint, result="ok"))
    db.commit()
    return summary
