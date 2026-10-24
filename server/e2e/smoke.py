"""End-to-end smoke test against a RUNNING server (real HTTP, real database, real WebSocket).

The repo tests (server/tests) build tables with create_all and use fake providers. This script
instead talks to a server started with uvicorn on a database built by the Alembic migrations, so it
checks the deployed shape: migrations, settings, routing, WebSocket and the golden path together.

The server must have DEMO_CONTROLS_ENABLED=true (this script resets and seeds the demo trader).

    # offline (CI): server runs with DEMO_MODE=true, no provider calls
    cd server && ../.venv/bin/python -m e2e.smoke --base-url http://127.0.0.1:8000

    # live providers: server runs with DEMO_MODE=false and a real LLM_API_KEY / STT in .env
    cd server && ../.venv/bin/python -m e2e.smoke --base-url http://127.0.0.1:8000 --voice clip.m4a

Exits non-zero on the first failed check. Never run it against a database you want to keep.
"""

import argparse
import asyncio
import json
import sys
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import websockets

DEMO_PHONE = "08030000001"


class SmokeFailure(AssertionError):
    pass


def check(condition: bool, label: str, detail: Any = None) -> None:
    if not condition:
        raise SmokeFailure(f"FAIL {label}: {json.dumps(detail, default=str)[:600]}")
    print(f"ok   {label}")


class Smoke:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.http = httpx.Client(base_url=self.base_url, timeout=60)
        self.headers: dict[str, str] = {}

    def message(self, text: str) -> dict[str, Any]:
        response = self.http.post(
            "/messages", headers=self.headers, json={"text": text, "client_message_id": str(uuid.uuid4())}
        )
        check(response.status_code == 200, f"POST /messages {text!r}", response.json())
        return response.json()

    def on_hand(self, name: str) -> Decimal:
        items = self.http.get("/inventory", headers=self.headers).json()
        return next(Decimal(str(item["quantity_on_hand"])) for item in items if item["name"] == name)

    async def run(self, clips: list[Path]) -> None:
        check(self.http.get("/health").status_code == 200, "GET /health")
        check(self.http.post("/demo/reset").status_code == 200, "POST /demo/reset")
        seed = self.http.post("/demo/seed")
        check(seed.status_code == 200, "POST /demo/seed", seed.json())
        token = seed.json()["token"]
        self.headers = {"Authorization": f"Bearer {token}"}
        rice_before = self.on_hand("rice")

        ws_url = self.base_url.replace("http", "ws", 1) + f"/ws?token={token}"
        async with websockets.connect(ws_url) as ws:
            await ws.send("ping")
            check(await asyncio.wait_for(ws.recv(), 5) == "pong", "WS ping/pong")

            # Golden path (PRD section 8): sale, credit sale with a due date, payment by nickname.
            sale = self.message("I sell two bags rice 120k")
            check(sale["status"] == "saved" and sale["entry"]["amount_ngn"] == 120000, "cash sale saved", sale)
            event = json.loads(await asyncio.wait_for(ws.recv(), 5))
            check(event["type"] == "entry_saved", "WS entry_saved event", event)

            credit = self.message("Mama Ngozi carry two bags rice on credit 120k, she go pay Friday")
            entry = credit.get("entry") or {}
            check(credit["status"] == "saved" and entry.get("type") == "credit_sale"
                  and entry.get("customer") == "Mama Ngozi" and entry.get("due_date"), "credit sale with due date", credit)

            payment = self.message("The rice woman pay me thirty k")
            entry = payment.get("entry") or {}
            check(payment["status"] == "saved" and entry.get("type") == "payment_received"
                  and entry.get("customer") == "Mama Ngozi" and entry.get("amount_ngn") == 30000,
                  "payment linked by nickname", payment)

            clarify = self.message("I sell two bags and half")
            check(clarify["status"] == "clarify", "missing amount asks a question", clarify)
            answered = self.message("145k")
            check(answered["status"] == "saved" and answered["entry"]["amount_ngn"] == 145000, "answer completes the entry", answered)

            # Figures come from the database.
            # The two rice sales move 4 bags; the "two bags and half" sale names no item, so moves none.
            check(self.on_hand("rice") == rice_before - Decimal(4), "rice stock moved by 4 bags",
                  {"before": rice_before, "after": self.on_hand("rice")})
            customers = self.http.get("/customers", headers=self.headers).json()
            ngozi = next((c for c in customers if c["canonical_name"] == "Mama Ngozi"), {})
            check(Decimal(str(ngozi.get("balance_ngn"))) >= Decimal(90000), "Mama Ngozi still owes at least 90k", ngozi)
            home = self.http.get("/home?period=today", headers=self.headers).json()
            check(Decimal(str(home["revenue_ngn"])) == Decimal(385000), "Home revenue = 120k + 120k + 145k", home)
            ask = self.http.post("/ask", headers=self.headers, json={"question": "Who owes me money?"}).json()
            check(ask["intent"] == "who_owes" and ask["customers"], "/ask who owes", ask)
            suggestions = self.http.get("/suggestions?item=garri", headers=self.headers).json()
            check(len(suggestions.get("suggestions", [])) == 3, "3 restock suggestions for garri", suggestions)

            for clip in clips:
                await self.voice(clip)

            # Consent: request, approve, collect the token once, read the totals-only summary.
            created = self.http.post("/access-requests", json={
                "trader_phone": DEMO_PHONE, "agent_name": "Smoke Lender", "purpose": "Working-capital loan check",
                "data_scopes": ["sales_total", "active_days", "total_owed"],
            }).json()
            decided = self.http.post(f"/access-requests/{created['request_id']}/approve",
                                     headers=self.headers, json={"approve": True})
            check(decided.status_code == 200, "trader approves the agent", decided.json())
            status = self.http.get(f"/access-requests/{created['request_id']}/status",
                                   headers={"X-Claim-Secret": created["claim_secret"]}).json()
            check(bool(status.get("access_token")), "agent collects its token", status)
            summary = self.http.get("/agent/summary", headers={"Authorization": f"Bearer {status['access_token']}"}).json()
            check("sales_total_ngn" in summary and "Mama Ngozi" not in json.dumps(summary), "agent summary is totals only", summary)

            # Logout ends the session and closes its socket.
            check(self.http.post("/auth/logout", headers=self.headers).status_code == 204, "POST /auth/logout")
            try:
                while True:
                    await asyncio.wait_for(ws.recv(), 5)  # skip events still in flight
            except websockets.ConnectionClosed as closed:
                check(closed.rcvd is not None and closed.rcvd.code == 4401, "WS closed with 4401 after logout")
            check(self.http.get("/profile", headers=self.headers).status_code == 401, "old token is rejected")

    async def voice(self, clip: Path) -> None:
        """Live STT check: prints the transcript; only the HTTP outcome is asserted, since the
        wording of a transcript cannot be predicted exactly."""
        with clip.open("rb") as audio:
            response = self.http.post(
                "/messages", headers=self.headers,
                data={"client_message_id": str(uuid.uuid4())},
                files={"audio": (clip.name, audio, _audio_type(clip))},
            )
        body = response.json()
        print(f"     voice transcript: {body.get('transcript') or (body.get('entry') or {}).get('raw_text')!r}")
        check(response.status_code == 200 and body.get("status") in {"saved", "clarify", "fallback"},
              f"voice message {clip.name}", body)


def _audio_type(clip: Path) -> str:
    return {".m4a": "audio/mp4", ".mp3": "audio/mpeg", ".wav": "audio/wav", ".ogg": "audio/ogg",
            ".webm": "audio/webm"}.get(clip.suffix.lower(), "application/octet-stream")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--voice", type=Path, action="append", help="audio clip to send (live STT); repeatable")
    args = parser.parse_args()
    try:
        asyncio.run(Smoke(args.base_url).run(args.voice or []))
    except SmokeFailure as failure:
        print(failure)
        sys.exit(1)
    print("smoke passed")


if __name__ == "__main__":
    main()
