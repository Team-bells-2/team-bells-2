from app.inventory.models import InventoryItem, StockMovement
from app.inventory.repositories.inventory_repository import InventoryRepository
from app.onboarding import services
from app.onboarding.models import Trader
from app.onboarding.repositories.location_repository import LocationRepository
from app.onboarding.repositories.session_repository import SessionRepository
from app.onboarding.repositories.trader_repository import TraderRepository
from app.onboarding.schemas import OnboardingRequest
from app.shared.errors import AppError


class OnboardingOrchestrator:
    def __init__(
        self,
        location_repository: LocationRepository,
        trader_repository: TraderRepository,
        session_repository: SessionRepository,
        inventory_repository: InventoryRepository,
    ):
        self.location_repository = location_repository
        self.trader_repository = trader_repository
        self.session_repository = session_repository
        self.inventory_repository = inventory_repository

    def onboard_trader(self, request: OnboardingRequest) -> tuple[str, Trader]:
        """Create the trader, its main items with opening stock, and a session in one transaction
        (FR-S21, BR-O1); return the plain token once."""
        location = self.location_repository.get_location_by_name(request.location_name)
        if location is None:
            raise AppError(422, "unknown_location", f"'{request.location_name}' is not a supported market or area.")
        if self.trader_repository.get_trader_by_phone(request.phone) is not None:
            raise AppError(409, "phone_taken", "A trader with this phone number already exists.")

        token = services.generate_session_token()
        try:
            trader = self.trader_repository.create_trader(services.build_trader(request, location))
            for main_item in request.items:
                item = self.inventory_repository.create_item(
                    InventoryItem(
                        trader_id=trader.id,
                        name=main_item.name,
                        unit=main_item.unit,
                        unit_cost_ngn=main_item.unit_cost_ngn,
                        reorder_level=main_item.reorder_level,
                        reorder_quantity=main_item.reorder_quantity,
                    )
                )
                if main_item.opening_quantity is not None:
                    self.inventory_repository.add_movement(
                        StockMovement(
                            inventory_item_id=item.id, quantity_change=main_item.opening_quantity, reason="opening"
                        )
                    )
            self.session_repository.create_session(trader.id, services.hash_token(token))
            self.trader_repository.commit()
        except Exception:
            self.trader_repository.rollback()
            raise
        self.trader_repository.refresh(trader)
        return token, trader

    def authenticate_trader(self, token: str | None) -> Trader:
        if not token:
            raise AppError(401, "missing_token", "A session token is required.")
        trader = self.session_repository.get_trader_by_active_token_hash(services.hash_token(token))
        if trader is None:
            raise AppError(401, "invalid_token", "The session token is invalid or revoked.")
        return trader
