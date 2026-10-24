"""WebSocket change notifications (FR-C6, FR-C13; BR-R1). Run: cd server && python -m unittest discover -s tests -t ."""

import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import update
from starlette.websockets import WebSocketDisconnect

from app.main import app
from app.onboarding.models import TraderSession
from app.shared.Infrastructure.db.session import get_db, get_session_factory
from app.shared.Infrastructure.realtime.hub import get_event_publisher
from tests.support import ApiTestCase, interpretation


class RecordingPublisher:
    def __init__(self) -> None:
        self.events: list[tuple[int, str, Any]] = []
        self.ended: list[int] = []

    def publish(self, trader_id: int, event: str, data: Any = None) -> None:
        self.events.append((trader_id, event, data))

    def end_session(self, session_id: int) -> None:
        self.ended.append(session_id)

    def types(self) -> list[str]:
        return [event for _, event, _ in self.events]


class PublishedEventsTest(ApiTestCase):
    """What is published, using a recording publisher (no sockets, no timing)."""

    def setUp(self) -> None:
        super().setUp()
        self.events = RecordingPublisher()
        app.dependency_overrides[get_event_publisher] = lambda: self.events
        self.trader_id, self.headers = self.onboard()
        self.rice = self.add_stock(self.trader_id, "rice", "10")
        self.beans = self.add_stock(self.trader_id, "beans", "1")

    def sale(self, message_id: str = "m1") -> None:
        self.send(self.headers, "sold 2 bag rice 20k", message_id,
                  interpretation(type="sale", item="rice", quantity=2, unit="bag", amount_text="20k"))

    def test_sale_publishes_the_entry_then_the_items_new_stock(self) -> None:
        self.sale()
        self.assertEqual(self.events.types(), ["entry_saved", "inventory_changed"])
        _, _, item = self.events.events[1]
        self.assertEqual((item.name, item.quantity_on_hand), ("rice", Decimal(8)))

    def test_a_replayed_retry_publishes_nothing(self) -> None:
        self.sale()
        self.events.events.clear()
        self.sale()  # same client_message_id
        self.assertEqual(self.events.events, [])

    def test_correction_to_another_item_announces_the_old_items_stock(self) -> None:
        self.sale()
        self.events.events.clear()
        # rice -> beans: beans has 1 bag, so the 2-bag sale is an oversell with no movement; rice goes back to 10.
        self.send(self.headers, "no I mean beans", "m2", {"intent": "correction", "confidence": 0.9, "item": "beans"})
        self.assertEqual(self.events.types(), ["entry_updated", "inventory_changed"])
        _, _, item = self.events.events[1]
        self.assertEqual((item.name, item.quantity_on_hand), ("rice", Decimal(10)))

    def test_a_clarifying_question_publishes_nothing(self) -> None:
        self.send(self.headers, "I sell rice", "m1", interpretation(type="sale", item="rice"))
        self.assertEqual(self.events.events, [])

    def test_events_go_only_to_the_acting_trader(self) -> None:
        self.sale()
        self.assertEqual({trader_id for trader_id, _, _ in self.events.events}, {self.trader_id})

    def test_logout_ends_the_sessions_sockets(self) -> None:
        self.client.post("/auth/logout", headers=self.headers)
        self.assertEqual(len(self.events.ended), 1)


class WebSocketTest(ApiTestCase):
    """Real sockets through the app."""

    def setUp(self) -> None:
        super().setUp()
        self.trader_id, self.headers = self.onboard()
        self.token = self.headers["Authorization"].split()[1]

    def assert_closed_with_4401(self, ws: Any) -> None:
        with self.assertRaises(WebSocketDisconnect) as closed:
            ws.receive_json()
        self.assertEqual(closed.exception.code, 4401)

    def test_bad_or_missing_token_closes_with_4401(self) -> None:
        for path in ("/ws", "/ws?token=nope"):
            with self.subTest(path=path), self.client.websocket_connect(path) as ws:
                self.assert_closed_with_4401(ws)

    def test_entry_saved_is_delivered(self) -> None:
        with self.client.websocket_connect(f"/ws?token={self.token}") as ws:
            self.send(self.headers, "sold beans 5k", "m1", interpretation(type="sale", item="beans", amount_text="5k"))
            message = ws.receive_json()
        self.assertEqual((message["type"], message["data"]["amount_ngn"]), ("entry_saved", 5000))
        self.assertIn("at", message)

    def test_ping_pong(self) -> None:
        with self.client.websocket_connect(f"/ws?token={self.token}") as ws:
            ws.send_text("ping")
            self.assertEqual(ws.receive_text(), "pong")

    def test_logout_closes_the_socket(self) -> None:
        with self.client.websocket_connect(f"/ws?token={self.token}") as ws:
            self.client.post("/auth/logout", headers=self.headers)
            self.assert_closed_with_4401(ws)

    def test_socket_closes_when_its_session_expires(self) -> None:
        with self.Session() as db:
            db.execute(update(TraderSession).values(expires_at=datetime.now(UTC) + timedelta(seconds=1)))
            db.commit()
        with self.client.websocket_connect(f"/ws?token={self.token}") as ws:
            time.sleep(1.2)
            ws.send_text("ping")
            self.assert_closed_with_4401(ws)

    def test_an_open_socket_holds_no_database_session(self) -> None:
        open_sessions = {"count": 0, "opened": 0}

        def no_request_session():
            raise AssertionError("the socket must not use the per-request get_db session")
            yield  # pragma: no cover

        def counting_factory():
            open_sessions["count"] += 1
            open_sessions["opened"] += 1
            db = self.Session()
            original_close = db.close

            def close() -> None:
                open_sessions["count"] -= 1
                original_close()

            db.close = close  # type: ignore[method-assign]
            return db

        app.dependency_overrides[get_session_factory] = lambda: counting_factory
        app.dependency_overrides[get_db] = no_request_session
        with self.client.websocket_connect(f"/ws?token={self.token}") as ws:
            ws.send_text("ping")
            self.assertEqual(ws.receive_text(), "pong")
            self.assertEqual((open_sessions["opened"], open_sessions["count"]), (1, 0))  # opened for auth, closed
