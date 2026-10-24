"""Shared test setup: the real FastAPI app on a throwaway database, with a fake LLM and a fake
speech-to-text provider, so tests need no API key and no network.

Default database: in-memory SQLite. Set TEST_DATABASE_URL to a THROWAWAY PostgreSQL database to
run the same tests against Postgres; its tables are dropped and recreated for every test.
"""

import os
import warnings
from collections.abc import Iterator
from decimal import Decimal
from typing import Any

# Deterministic settings for tests; real environment variables still win.
_TEST_SETTINGS = {
    "DATABASE_URL": "postgresql+psycopg://test:test@localhost:5432/oja_test_unused",
    "DB_ECHO": "false",
    "DB_POOL_SIZE": "5",
    "DB_MAX_OVERFLOW": "10",
    "LLM_BASE_URL": "http://llm.invalid/v1",
    "LLM_API_KEY": "test-key",
    "LLM_MODEL": "test-model",
    "LLM_TIMEOUT_SECONDS": "5",
    "LLM_MAX_TOKENS": "400",
    "LLM_RATE_LIMIT_DEFAULT_WAIT_SECONDS": "1.5",
    "LLM_RATE_LIMIT_MAX_WAIT_SECONDS": "3",
    "STT_BASE_URL": "http://stt.invalid",
    "STT_INFERENCE_PATH": "/v1/audio/transcriptions",
    "STT_API_KEY": "",
    "STT_MODEL": "whisper-1",
    "STT_TIMEOUT_SECONDS": "5",
    "STT_MAX_UPLOAD_MB": "1",
    "CONFIDENCE_THRESHOLD": "0.7",
    "CUSTOMER_MATCH_LINK_CONFIDENCE": "0.85",
    "CUSTOMER_MATCH_CONFIRM_CONFIDENCE": "0.5",
    "SUGGESTION_WEIGHT_DISTANCE": "0.25",
    "SUGGESTION_WEIGHT_RATING": "0.2",
    "SUGGESTION_WEIGHT_QUALITY": "0.15",
    "SUGGESTION_WEIGHT_COST": "0.25",
    "SUGGESTION_WEIGHT_QUANTITY": "0.15",
    "SUGGESTION_DISTANCE_HALF_KM": "10",
    "SUGGESTION_QUALITY_SCORE_A": "1.0",
    "SUGGESTION_QUALITY_SCORE_B": "0.7",
    "SUGGESTION_QUALITY_SCORE_C": "0.4",
    "DEMO_MODE": "false",
    "DEMO_CONTROLS_ENABLED": "false",
    "SESSION_TOKEN_TTL_DAYS": "30",
    "AUTH_MAX_FAILED_LOGINS": "5",
    "AUTH_LOCK_MINUTES": "5",
    "ACCESS_TOKEN_TTL_MINUTES": "43200",
    "CORS_ORIGINS": "[]",
}
for _key, _value in _TEST_SETTINGS.items():
    os.environ.setdefault(_key, _value)

warnings.filterwarnings("ignore", message=".*Decimal.*")  # SQLite stores Numeric as float
warnings.filterwarnings("ignore", category=DeprecationWarning)

import unittest  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, func, select  # noqa: E402
from sqlalchemy.engine import Engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import app.consent.models  # noqa: E402, F401  (register every table on Base.metadata)
import app.customers.models  # noqa: E402, F401
import app.inventory.models  # noqa: E402, F401
import app.ledger.models  # noqa: E402, F401
import app.onboarding.models  # noqa: E402, F401
import app.suggestions.models  # noqa: E402, F401
from app.customers.repositories.customer_repository import CustomerRepository  # noqa: E402
from app.demo.orchestrator import DemoOrchestrator  # noqa: E402
from app.demo.repositories.seed_repository import SeedRepository  # noqa: E402
from app.inventory.models import InventoryItem, StockMovement  # noqa: E402
from app.inventory.repositories.inventory_repository import InventoryRepository  # noqa: E402
from app.main import app  # noqa: E402
from app.onboarding.repositories.location_repository import LocationRepository  # noqa: E402
from app.onboarding.repositories.session_repository import SessionRepository  # noqa: E402
from app.onboarding.repositories.trader_repository import TraderRepository  # noqa: E402
from app.shared.Infrastructure.db.base import Base  # noqa: E402
from app.shared.Infrastructure.db.session import get_db, get_session_factory  # noqa: E402
from app.shared.Infrastructure.llm.client import LLMError, get_llm_client  # noqa: E402
from app.shared.Infrastructure.SST.client import TranscriptionError, get_transcriber  # noqa: E402


class FakeLLM:
    """Returns queued replies in order. Queue a dict (model JSON) or an Exception to raise."""

    def __init__(self) -> None:
        self.queue: list[dict[str, Any] | Exception] = []
        self.calls = 0

    def complete_json(self, system_prompt: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls += 1
        if not self.queue:
            raise LLMError("FakeLLM: no reply queued")
        reply = self.queue.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


class FakeTranscriber:
    def __init__(self) -> None:
        self.text = "I sell one bag rice ten k"
        self.fail = False

    def transcribe(self, audio: bytes, content_type: str) -> str:
        if self.fail:
            raise TranscriptionError("FakeTranscriber: failure requested")
        return self.text


def demo_orchestrator(db: Session) -> DemoOrchestrator:
    return DemoOrchestrator(
        SeedRepository(db), LocationRepository(db), TraderRepository(db), SessionRepository(db),
        InventoryRepository(db), CustomerRepository(db), session_ttl_days=30,
    )


def interpretation(**fields: Any) -> dict[str, Any]:
    """A valid model reply for an entry; override any field."""
    return {"intent": "entry", "confidence": 0.95, **fields}


def _make_engine() -> Engine:
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        return create_engine(url)
    return create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)


class ApiTestCase(unittest.TestCase):
    """Fresh database, fake providers and a TestClient for every test."""

    def setUp(self) -> None:
        self.engine = _make_engine()
        Base.metadata.drop_all(self.engine)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, expire_on_commit=False)
        self.llm = FakeLLM()
        self.stt = FakeTranscriber()

        def override_db() -> Iterator[Session]:
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_llm_client] = lambda: self.llm
        app.dependency_overrides[get_transcriber] = lambda: self.stt
        app.dependency_overrides[get_session_factory] = lambda: self.Session
        self.client = TestClient(app)
        with self.Session() as db:
            demo_orchestrator(db).seed_reference_data()

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        if os.environ.get("TEST_DATABASE_URL"):
            Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def onboard(self, phone: str = "08031234567", location: str = "Mile 12") -> tuple[int, dict[str, str]]:
        """Create a trader; returns (trader_id, auth headers)."""
        response = self.client.post(
            "/onboarding",
            json={
                "name": "Ada Obi",
                "phone": phone,
                "business_name": "Ada Foods",
                "sector": "foodstuff",
                "location_name": location,
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        body = response.json()
        return body["trader"]["id"], {"Authorization": f"Bearer {body['token']}"}

    def add_stock(self, trader_id: int, name: str, opening: str, reorder_level: str = "0", reorder_quantity: str = "0") -> int:
        """Inventory item with an opening movement (until the inventory write endpoints exist)."""
        with self.Session() as db:
            item = InventoryItem(
                trader_id=trader_id,
                name=name,
                unit="bag",
                reorder_level=Decimal(reorder_level),
                reorder_quantity=Decimal(reorder_quantity),
            )
            db.add(item)
            db.flush()
            db.add(StockMovement(inventory_item_id=item.id, quantity_change=Decimal(opening), reason="opening"))
            db.commit()
            return item.id

    def on_hand(self, item_id: int) -> Decimal:
        with self.Session() as db:
            total = db.scalar(
                select(func.coalesce(func.sum(StockMovement.quantity_change), 0)).where(
                    StockMovement.inventory_item_id == item_id
                )
            )
            return Decimal(str(total))

    def send(self, headers: dict[str, str], text: str, message_id: str, reply: dict[str, Any] | Exception | None = None):
        """POST /messages with one queued model reply."""
        if reply is not None:
            self.llm.queue.append(reply)
        return self.client.post("/messages", headers=headers, json={"text": text, "client_message_id": message_id})
