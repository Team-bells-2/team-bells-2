from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.inventory.models import InventoryItem, StockMovement
from app.onboarding.models import SessionToken, Trader
from app.onboarding.schemas import OnboardingRequest, OnboardingResponse, ProfileResponse, ProfileUpdate
from app.shared.Infrastructure.db.session import get_db
from app.shared.auth import get_current_trader, issue_session_token

router = APIRouter(tags=["onboarding", "profile"])


@router.post("/onboarding", response_model=OnboardingResponse, status_code=201)
def onboard(payload: OnboardingRequest, db: Session = Depends(get_db)) -> OnboardingResponse:
    existing = db.scalar(select(Trader).where(Trader.phone == payload.phone.strip()))
    if existing:
        raise HTTPException(status_code=409, detail={"error": {"code": "phone_exists", "message": "A trader with this phone number already exists."}})
    trader = Trader(
        name=payload.name.strip(), phone=payload.phone.strip(), business_name=payload.business_name.strip(),
        sector=payload.sector.strip(), location_name=payload.location_name.strip(),
        latitude=payload.latitude, longitude=payload.longitude,
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
    db.refresh(trader)
    session_token = db.scalar(
        select(SessionToken).where(SessionToken.trader_id == trader.id).order_by(SessionToken.id.desc())
    )
    return OnboardingResponse(trader_id=trader.id, session_token=token, expires_at=session_token.expires_at.isoformat())


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
    return ProfileResponse.model_validate(trader, from_attributes=True)
