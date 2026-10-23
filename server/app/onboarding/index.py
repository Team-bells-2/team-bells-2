from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.inventory.models import InventoryItem, StockMovement
from app.onboarding.models import SessionToken, Trader
from app.onboarding.schemas import ChangePinRequest, LoginRequest, OnboardingRequest, OnboardingResponse, ProfileResponse, ProfileUpdate
from app.shared.Infrastructure.db.session import get_db
from app.shared.auth import get_current_session, get_current_trader, hash_pin, issue_session_token, verify_pin
from app.shared.realtime import publish

router = APIRouter(tags=["onboarding", "profile", "auth"])

MAX_FAILED_LOGINS = 5
LOCK_MINUTES = 5
# Checked against unknown phone numbers so a wrong phone takes as long as a wrong PIN.
_DUMMY_PIN_HASH = hash_pin("000000")


def _error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"error": {"code": code, "message": message}})


def _session_response(db: Session, trader: Trader, token: str) -> OnboardingResponse:
    session_token = db.scalar(select(SessionToken).where(SessionToken.trader_id == trader.id).order_by(SessionToken.id.desc()))
    return OnboardingResponse(trader_id=trader.id, session_token=token, expires_at=session_token.expires_at.isoformat())


@router.post("/onboarding", response_model=OnboardingResponse, status_code=201)
@router.post("/auth/signup", response_model=OnboardingResponse, status_code=201)
def onboard(payload: OnboardingRequest, db: Session = Depends(get_db)) -> OnboardingResponse:
    existing = db.scalar(select(Trader).where(Trader.phone == payload.phone.strip()))
    if existing:
        raise _error(409, "phone_exists", "A trader with this phone number already exists. Log in instead.")
    trader = Trader(
        name=payload.name.strip(), phone=payload.phone.strip(), business_name=payload.business_name.strip(),
        sector=payload.sector.strip(), location_name=payload.location_name.strip(),
        latitude=payload.latitude, longitude=payload.longitude, pin_hash=hash_pin(payload.pin),
    )
    db.add(trader)
    db.flush()
    for opening_item in payload.items:
        item = InventoryItem(
            trader_id=trader.id, name=opening_item.name.strip(), unit=opening_item.unit.strip(),
            unit_cost_ngn=opening_item.unit_cost_ngn, reorder_level=opening_item.reorder_level,
            reorder_quantity=opening_item.reorder_quantity,
        )
        db.add(item)
        db.flush()
        if opening_item.opening_quantity:
            db.add(StockMovement(
                inventory_item_id=item.id,
                quantity_change=opening_item.opening_quantity,
                reason="opening",
            ))
    token = issue_session_token(db, trader)
    db.commit()
    return _session_response(db, trader, token)


@router.post("/auth/login", response_model=OnboardingResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> OnboardingResponse:
    trader = db.scalar(select(Trader).where(Trader.phone == payload.phone.strip()))
    now = datetime.now(UTC)
    if trader is None:
        verify_pin(payload.pin, _DUMMY_PIN_HASH)
        raise _error(401, "invalid_credentials", "Phone number or PIN is wrong.")
    locked_until = trader.locked_until.replace(tzinfo=UTC) if trader.locked_until and trader.locked_until.tzinfo is None else trader.locked_until
    if locked_until and locked_until > now:
        minutes = max(1, round((locked_until - now).total_seconds() / 60))
        raise _error(429, "account_locked", f"Too many wrong PINs. Try again in {minutes} minute{'s' if minutes > 1 else ''}.")
    if not verify_pin(payload.pin, trader.pin_hash):
        trader.failed_logins = (trader.failed_logins or 0) + 1
        if trader.failed_logins >= MAX_FAILED_LOGINS:
            trader.failed_logins = 0
            trader.locked_until = now + timedelta(minutes=LOCK_MINUTES)
        db.commit()
        raise _error(401, "invalid_credentials", "Phone number or PIN is wrong.")
    trader.failed_logins = 0
    trader.locked_until = None
    token = issue_session_token(db, trader)
    db.commit()
    return _session_response(db, trader, token)


@router.post("/auth/logout", status_code=204)
def logout(session_token: SessionToken = Depends(get_current_session), db: Session = Depends(get_db)) -> None:
    """Ends this device's session only; other logged-in devices stay signed in."""
    session_token.revoked_at = datetime.now(UTC)
    db.commit()


@router.post("/auth/change-pin", status_code=204)
def change_pin(payload: ChangePinRequest, trader: Trader = Depends(get_current_trader), db: Session = Depends(get_db)) -> None:
    if not verify_pin(payload.current_pin, trader.pin_hash):
        raise _error(401, "invalid_credentials", "Current PIN is wrong.")
    trader.pin_hash = hash_pin(payload.new_pin)
    db.commit()


@router.get("/profile", response_model=ProfileResponse)
def get_profile(trader: Trader = Depends(get_current_trader)) -> ProfileResponse:
    return ProfileResponse.model_validate(trader, from_attributes=True)


@router.patch("/profile", response_model=ProfileResponse)
def update_profile(
    payload: ProfileUpdate,
    trader: Trader = Depends(get_current_trader),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(trader, field, value.strip() if isinstance(value, str) else value)
    db.commit()
    db.refresh(trader)
    profile = ProfileResponse.model_validate(trader, from_attributes=True)
    publish(trader.id, "profile_updated", profile)
    return profile
