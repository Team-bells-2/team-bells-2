from datetime import UTC, datetime, timedelta

from app.inventory.models import InventoryItem, StockMovement
from app.inventory.repositories.inventory_repository import InventoryRepository
from app.onboarding import services
from app.onboarding.models import Trader, TraderSession
from app.onboarding.repositories.location_repository import LocationRepository
from app.onboarding.repositories.session_repository import SessionRepository
from app.onboarding.repositories.trader_repository import TraderRepository
from app.onboarding.schemas import OnboardingRequest
from app.shared.errors import AppError
from app.shared.Infrastructure.realtime.hub import EventPublisher
from app.shared.periods import as_utc


class OnboardingOrchestrator:
    """Sign-up, sessions and the optional PIN login (FR-S21, D7; BR-O1, BR-O3, BR-O4)."""

    def __init__(
        self,
        location_repository: LocationRepository,
        trader_repository: TraderRepository,
        session_repository: SessionRepository,
        inventory_repository: InventoryRepository,
        session_ttl_days: int,
        max_failed_logins: int,
        lock_minutes: int,
        events: EventPublisher,
    ):
        self.location_repository = location_repository
        self.trader_repository = trader_repository
        self.session_repository = session_repository
        self.inventory_repository = inventory_repository
        self.session_ttl_days = session_ttl_days
        self.max_failed_logins = max_failed_logins
        self.lock_minutes = lock_minutes
        self.events = events

    def onboard_trader(self, request: OnboardingRequest) -> tuple[str, Trader]:
        """Create the trader, its main items with opening stock, and a session in one transaction
        (FR-S21, BR-O1); return the plain token once."""
        location = self.location_repository.get_location_by_name(request.location_name)
        if location is None:
            raise AppError(422, "unknown_location", f"'{request.location_name}' is not a supported market or area.")
        if self.trader_repository.get_trader_by_phone(request.phone) is not None:
            raise AppError(409, "phone_taken", "A trader with this phone number already exists.")

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
            token = self._start_session(trader)
            self.trader_repository.commit()
        except Exception:
            self.trader_repository.rollback()
            raise
        self.trader_repository.refresh(trader)
        return token, trader

    def login(self, phone: str, pin: str) -> tuple[str, Trader]:
        """Phone + PIN. A wrong phone, a missing PIN and a wrong PIN look and take the same (BR-O3)."""
        now = datetime.now(UTC)
        trader = self.trader_repository.get_trader_by_phone(phone)
        if trader is None or trader.pin_hash is None:
            services.verify_pin(pin, services.DUMMY_PIN_HASH)
            raise AppError(401, "invalid_credentials", "Phone number or PIN is wrong.")
        if trader.locked_until is not None and as_utc(trader.locked_until) > now:
            minutes_left = max(1, round((as_utc(trader.locked_until) - now).total_seconds() / 60))
            raise AppError(429, "account_locked", services.lock_message(minutes_left))

        try:
            if not services.verify_pin(pin, trader.pin_hash):
                trader.failed_logins = (trader.failed_logins or 0) + 1
                if trader.failed_logins >= self.max_failed_logins:
                    trader.failed_logins = 0
                    trader.locked_until = now + timedelta(minutes=self.lock_minutes)
                self.trader_repository.commit()
                raise AppError(401, "invalid_credentials", "Phone number or PIN is wrong.")
            trader.failed_logins = 0
            trader.locked_until = None
            token = self._start_session(trader)
            self.trader_repository.commit()
        except AppError:
            raise
        except Exception:
            self.trader_repository.rollback()
            raise
        self.trader_repository.refresh(trader)
        return token, trader

    def logout(self, session: TraderSession) -> None:
        """Ends this device's session only; the trader's other devices stay signed in."""
        try:
            session.revoked_at = datetime.now(UTC)
            self.session_repository.commit()
        except Exception:
            self.session_repository.rollback()
            raise
        self.events.end_session(session.id)  # open sockets of this session close now

    def change_pin(self, trader: Trader, current_pin: str | None, new_pin: str) -> None:
        """The current PIN is required once one exists; the first PIN is set without it."""
        if trader.pin_hash is not None and not (current_pin and services.verify_pin(current_pin, trader.pin_hash)):
            raise AppError(401, "invalid_credentials", "Current PIN is wrong.")
        try:
            trader.pin_hash = services.hash_pin(new_pin)
            self.trader_repository.commit()
        except Exception:
            self.trader_repository.rollback()
            raise

    def authenticate_session(self, token: str | None) -> TraderSession:
        """Not revoked and not expired (BR-O4). Read-only."""
        if not token:
            raise AppError(401, "missing_token", "A session token is required.")
        session = self.session_repository.get_session_by_token_hash(services.hash_token(token))
        if session is None or session.revoked_at is not None or self.session_expires_at(session) <= datetime.now(UTC):
            raise AppError(401, "invalid_token", "The session token is invalid, expired or revoked.")
        return session

    def session_expires_at(self, session: TraderSession) -> datetime:
        return services.effective_expiry(session.expires_at, session.created_at, self.session_ttl_days)

    def authenticate_trader(self, token: str | None) -> Trader:
        session = self.authenticate_session(token)
        trader = self.session_repository.get_trader(session.trader_id)
        if trader is None:
            raise AppError(401, "invalid_token", "The session token is invalid, expired or revoked.")
        return trader

    def _start_session(self, trader: Trader) -> str:
        """A new session with its expiry (BR-O4); the plain token is returned once."""
        token = services.generate_session_token()
        expires_at = services.session_expiry(datetime.now(UTC), self.session_ttl_days)
        self.session_repository.create_session(trader.id, services.hash_token(token), expires_at)
        return token
