"""Eval harness for the message pipeline (FR-S18 to S20).

Runs every case in cases.json through POST /messages on a fresh in-memory database seeded with the
demo trader (customers with nicknames, rice/beans/garri/oil in stock), and compares the reply with the
expected entry or clarifying question. Prints "N of 40 correct" and the failures, and writes the
results to eval/results.json for the deck.

    cd server && ../.venv/bin/python -m eval.run_eval          # offline: DEMO_MODE rules, no provider calls
    cd server && ../.venv/bin/python -m eval.run_eval --live   # the LLM configured in .env

Settings are read from the root .env as usual.
"""

import argparse
import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.consent.models  # noqa: F401  (register every table)
import app.customers.models  # noqa: F401
import app.inventory.models  # noqa: F401
import app.ledger.models  # noqa: F401
import app.onboarding.models  # noqa: F401
import app.suggestions.models  # noqa: F401
from app.ai.dependencies import get_ai_orchestrator
from app.ai.orchestrator import AIOrchestrator
from app.customers.repositories.customer_repository import CustomerRepository
from app.demo.orchestrator import DemoOrchestrator
from app.demo.repositories.seed_repository import SeedRepository
from app.inventory.repositories.inventory_repository import InventoryRepository
from app.ledger.services import resolve_due_date
from app.main import app
from app.onboarding.repositories.location_repository import LocationRepository
from app.onboarding.repositories.session_repository import SessionRepository
from app.onboarding.repositories.trader_repository import TraderRepository
from app.shared.env import settings
from app.shared.Infrastructure.db.base import Base
from app.shared.Infrastructure.db.session import get_db, get_session_factory
from app.shared.Infrastructure.llm.client import get_llm_client
from app.shared.matching import match_key
from app.shared.periods import LAGOS

EVAL_DIR = Path(__file__).resolve().parent
CASES_FILE = EVAL_DIR / "cases.json"
RESULTS_FILE = EVAL_DIR / "results.json"


def _fresh_trader(live: bool) -> tuple[TestClient, dict[str, str]]:
    """A new database with the demo trader; returns a client and the trader's auth headers."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_db() -> Iterator[Session]:
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_session_factory] = lambda: factory
    app.dependency_overrides[get_ai_orchestrator] = lambda: AIOrchestrator(get_llm_client(), demo_mode=not live)
    with factory() as db:
        demo = DemoOrchestrator(
            SeedRepository(db), LocationRepository(db), TraderRepository(db), SessionRepository(db),
            InventoryRepository(db), CustomerRepository(db), settings.SESSION_TOKEN_TTL_DAYS,
        ).seed_demo()
    return TestClient(app), {"Authorization": f"Bearer {demo.token}"}


def _send(client: TestClient, headers: dict[str, str], text: str, message_id: str) -> dict[str, Any]:
    response = client.post("/messages", headers=headers, json={"text": text, "client_message_id": message_id})
    body = response.json()
    if response.status_code != 200:
        return {"status": f"http_{response.status_code}", "message": body.get("error", {}).get("message", "")}
    return body


def _mismatches(expected: dict[str, Any], got: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    if got.get("status") != expected["status"]:
        problems.append(f"status: expected {expected['status']}, got {got.get('status')}")
    if "message_contains" in expected and expected["message_contains"] not in (got.get("message") or ""):
        problems.append(f"message: expected to contain {expected['message_contains']!r}, got {got.get('message')!r}")
    entry = got.get("entry") or {}
    for field, want in expected.get("entry", {}).items():
        if field == "due":
            want_date = resolve_due_date(want, datetime.now(LAGOS).date())
            have = entry.get("due_date")
            if want_date is None or have != want_date.isoformat():
                problems.append(f"due_date: expected {want_date}, got {have}")
            continue
        have = entry.get(field)
        if isinstance(want, int | float):
            same = isinstance(have, int | float) and abs(float(have) - float(want)) < 0.005
        elif field in {"item", "unit"}:
            same = isinstance(have, str) and match_key(have) == match_key(want)
        else:
            same = have == want
        if not same:
            problems.append(f"{field}: expected {want!r}, got {have!r}")
    return problems


def run(live: bool) -> dict[str, Any]:
    cases: list[dict[str, Any]] = json.loads(CASES_FILE.read_text(encoding="utf-8"))
    results = []
    for case in cases:
        client, headers = _fresh_trader(live)
        for index, setup_text in enumerate(case.get("setup", [])):
            _send(client, headers, setup_text, f"{case['id']}-setup-{index}")
        got = _send(client, headers, case["message"], case["id"])
        problems = _mismatches(case["expected"], got)
        results.append({
            "id": case["id"], "category": case["category"], "hard": case.get("hard", False),
            "message": case["message"], "ok": not problems, "problems": problems,
            "expected": case["expected"], "got": {key: got.get(key) for key in ("status", "message", "entry")},
        })
    app.dependency_overrides.clear()
    correct = sum(result["ok"] for result in results)
    return {
        "mode": "live" if live else "offline (DEMO_MODE rules)",
        "run_at": datetime.now(UTC).isoformat(),
        "correct": correct,
        "total": len(results),
        "hard_correct": sum(r["ok"] for r in results if r["hard"]),
        "hard_total": sum(1 for r in results if r["hard"]),
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--live", action="store_true", help="use the LLM from .env instead of the offline rules")
    report = run(live=parser.parse_args().live)
    RESULTS_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{report['correct']} of {report['total']} correct ({report['mode']}); "
          f"hard cases {report['hard_correct']} of {report['hard_total']}")
    for result in report["results"]:
        if not result["ok"]:
            print(f"- {result['id']} [{result['category']}{', hard' if result['hard'] else ''}] {result['message']!r}")
            for problem in result["problems"]:
                print(f"    {problem}")
    print(f"Results written to {RESULTS_FILE.relative_to(EVAL_DIR.parent)}")


if __name__ == "__main__":
    main()
