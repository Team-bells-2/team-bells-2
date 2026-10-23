"""Real-time push to the trader's app and the dashboard over WebSocket.

Clients connect to /ws?token=<session token>. Actions still go through the REST endpoints;
this channel only tells connected clients that something changed, so they update at once.
One process only: run a single uvicorn worker.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder

from app.shared.Infrastructure.db.session import SessionLocal

router = APIRouter(tags=["realtime"])
logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[int, set[WebSocket]] = defaultdict(set)
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def connect(self, trader_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[trader_id].add(websocket)

    def disconnect(self, trader_id: int, websocket: WebSocket) -> None:
        self._connections[trader_id].discard(websocket)

    def count(self, trader_id: int) -> int:
        return len(self._connections[trader_id])

    async def _send(self, trader_id: int, message: dict[str, Any]) -> None:
        for websocket in list(self._connections[trader_id]):
            try:
                await websocket.send_json(message)
            except Exception:  # A dropped client must never break the request that published.
                self.disconnect(trader_id, websocket)

    def publish(self, trader_id: int, event: str, data: Any = None) -> None:
        """Safe to call from the sync endpoints (FastAPI's thread pool). Call it after db.commit()."""
        if self._loop is None or not self._connections[trader_id]:
            return
        message = {"type": event, "data": jsonable_encoder(data), "at": datetime.now(UTC).isoformat()}
        try:
            asyncio.run_coroutine_threadsafe(self._send(trader_id, message), self._loop)
        except RuntimeError:
            logger.warning("Realtime loop unavailable; dropped %s event", event)


manager = ConnectionManager()
publish = manager.publish


@router.websocket("/ws")
async def realtime(websocket: WebSocket, token: str = "") -> None:
    from app.shared.auth import trader_for_token

    with SessionLocal() as db:
        trader = trader_for_token(db, token)
        trader_id = trader.id if trader else None
    if trader_id is None:
        await websocket.close(code=4401, reason="Invalid or expired session token")
        return
    await manager.connect(trader_id, websocket)
    await websocket.send_json({"type": "connected", "data": {"trader_id": trader_id}, "at": datetime.now(UTC).isoformat()})
    try:
        while True:
            # Clients may send "ping" to keep mobile connections alive.
            if await websocket.receive_text() == "ping":
                await websocket.send_json({"type": "pong", "data": None, "at": datetime.now(UTC).isoformat()})
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(trader_id, websocket)
