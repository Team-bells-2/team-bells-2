"""Real-time push to a trader's connected clients (the app, the judges' dashboard) over WebSocket.

Clients connect to /ws?token=<session token>. Actions still go through the REST endpoints; this
channel only tells connected clients that something changed, so they refresh at once (FR-C6, FR-C13).
Events are published after the change is committed. A socket is closed (code 4401) when its session
is logged out or has expired. Connections live in this process, so run a single uvicorn worker.
"""

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from fastapi import WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder

logger = logging.getLogger("oja.realtime")

SESSION_ENDED_CODE = 4401


class EventPublisher(Protocol):
    def publish(self, trader_id: int, event: str, data: Any = None) -> None: ...

    def end_session(self, session_id: int) -> None: ...


@dataclass(eq=False)
class _Client:
    websocket: WebSocket
    session_id: int
    expires_at: datetime  # timezone-aware UTC

    def expired(self, now: datetime) -> bool:
        return self.expires_at <= now


class RealtimeHub:
    def __init__(self) -> None:
        self._clients: dict[int, set[_Client]] = defaultdict(set)
        self._loop: asyncio.AbstractEventLoop | None = None
        # Strong references to running sends/closes; asyncio keeps only weak ones.
        self._tasks: set[asyncio.Task[None]] = set()

    async def connect(self, trader_id: int, session_id: int, expires_at: datetime, websocket: WebSocket) -> None:
        # Endpoints run in worker threads; events are handed to the event loop the sockets live on.
        self._loop = asyncio.get_running_loop()
        await websocket.accept()
        self._clients[trader_id].add(_Client(websocket, session_id, expires_at))

    def disconnect(self, trader_id: int, websocket: WebSocket) -> None:
        clients = self._clients.get(trader_id)
        if clients is None:
            return
        for client in [c for c in clients if c.websocket is websocket]:
            clients.discard(client)
        if not clients:
            self._clients.pop(trader_id, None)

    def connection_count(self, trader_id: int) -> int:
        return len(self._clients.get(trader_id, ()))

    def is_expired(self, trader_id: int, websocket: WebSocket) -> bool:
        now = datetime.now(UTC)
        return any(c.expired(now) for c in self._clients.get(trader_id, ()) if c.websocket is websocket)

    def publish(self, trader_id: int, event: str, data: Any = None) -> None:
        """Safe to call from any thread, after the commit. Does nothing when nobody is connected."""
        message = {"type": event, "data": jsonable_encoder(data), "at": datetime.now(UTC).isoformat()}
        self._call_on_loop(self._start_send, trader_id, message)

    def end_session(self, session_id: int) -> None:
        """Close every socket opened with this session (after logout). Safe from any thread."""
        self._call_on_loop(self._start_close_session, session_id)

    def _call_on_loop(self, callback: Any, *args: Any) -> None:
        loop = self._loop
        if loop is None or loop.is_closed() or not self._clients:
            return
        try:
            loop.call_soon_threadsafe(callback, *args)
        except RuntimeError:
            logger.warning("Realtime loop unavailable; dropped a realtime call")

    def _track(self, coroutine: Any) -> None:
        task = asyncio.get_running_loop().create_task(coroutine)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    def _start_send(self, trader_id: int, message: dict[str, Any]) -> None:
        if self._clients.get(trader_id):
            self._track(self._send(trader_id, message))

    def _start_close_session(self, session_id: int) -> None:
        for trader_id, clients in list(self._clients.items()):
            for client in [c for c in clients if c.session_id == session_id]:
                self._track(self._close(trader_id, client))

    async def _send(self, trader_id: int, message: dict[str, Any]) -> None:
        now = datetime.now(UTC)
        for client in list(self._clients.get(trader_id, ())):
            if client.expired(now):
                await self._close(trader_id, client)
                continue
            try:
                await client.websocket.send_json(message)
            except (OSError, RuntimeError, WebSocketDisconnect):
                self.disconnect(trader_id, client.websocket)

    async def _close(self, trader_id: int, client: _Client) -> None:
        self.disconnect(trader_id, client.websocket)
        try:
            await client.websocket.close(code=SESSION_ENDED_CODE)
        except (OSError, RuntimeError, WebSocketDisconnect):
            pass


hub = RealtimeHub()


def get_event_publisher() -> EventPublisher:
    return hub
