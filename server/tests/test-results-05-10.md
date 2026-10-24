# Backend test results — 2026-10-24 05:10 (+01:00)

## Result

**Automated backend suite: PASS on SQLite and PostgreSQL (173 tests on each).**  
**PostgreSQL migrations, downgrade/re-upgrade, and reference seed idempotency: PASS.**  
**Live-server E2E smoke on PostgreSQL: PASS.**  
**Offline evaluation: 37/40 (target >=30 met; 3 case mismatches listed below).**

No backend application code, tests, CI workflow, or other user changes were modified during this run. I updated [test-steps.md](./test-steps.md) to reflect the current CI coverage and commands.

## Updated workflow reviewed

The current [backend-tests.yml](../../.github/workflows/backend-tests.yml) now has:

- SQLite unit/API tests.
- A PostgreSQL 16 job that upgrades migrations, checks for schema drift, downgrades to base and reapplies migrations, seeds reference data twice, runs the same test suite using a separate test database, and runs the offline `e2e.smoke` script against a live Uvicorn server.
- Push, pull-request and manual workflow triggers.

The PostgreSQL job uses a distinct application database and test database; I preserved that separation locally. CI runs the smoke in `DEMO_MODE` and does not call live LLM/STT services or upload audio.

## Checks run

Environment: branch `oja`, local Python 3.14.8, local PostgreSQL 16 container. The repository's GitHub workflow configures Python 3.12; that exact interpreter was not available/run locally.

### SQLite backend suite

Command: `make test`

**Result:** 173 tests passed in 10.598 seconds; 0 failures, 0 errors.

### PostgreSQL workflow sequence

Used two new isolated databases, `oja_ci_validation_20261024` (migrations and live server) and `oja_ci_validation_test_20261024` (test suite). The app database configured in `.env` was not used.

Passed all of the following:

- `alembic upgrade head` — all four migrations applied.
- `alembic check` — `No new upgrade operations detected.`
- `alembic downgrade base`, then `alembic upgrade head`.
- `python -m app.demo.index` twice — both seed runs passed.
- Full `unittest` discovery on PostgreSQL using the separate test DB — 173 tests passed in 35.541 seconds; 0 failures, 0 errors.

### Live-server E2E smoke

Started Uvicorn against the migrated app database with `DEMO_MODE=true` and `DEMO_CONTROLS_ENABLED=true`, then ran:

```sh
cd server
../.venv/bin/python -m e2e.smoke --base-url http://127.0.0.1:8000
```

**Result: passed.** Verified health, demo reset/seed, WebSocket ping and event delivery/closure, cash and credit sales, due date, nickname payment, clarification, stock/customer/Home figures, `/ask`, suggestions, consent approval/claim and totals-only summary, logout, and rejection of the old session token. The smoke reset/seed affected only the isolated app database.

### Offline extraction evaluation

Command: `make eval`

**Result:** 37/40 correct, including 7/10 hard cases. The documented >=30/40 target was met. Mismatches:

| Case | Expected | Actual |
|---|---|---|
| `c21` — “Iya Sade send 15k transfer for her debt” | `payment_received` | `sale` |
| `c27` — “Shop rent 50k” | `expense` | `sale` |
| `c29` — “Market levy 1,500” | `expense` | `sale` |

These are reported evaluation mismatches, not failed test-suite assertions. The command exited successfully. `make eval-live` was not run.

## Warnings and remaining unverified items

- Both test runs emitted a `StarletteDeprecationWarning` about `httpx` usage in `starlette.testclient`. Tests still passed.
- The SQLite run emitted Python `ResourceWarning`s for unclosed SQLite connections. They did not fail the run; this is worth tracking separately.
- The smoke did not receive `--voice` clips. Real STT, transcript accuracy, live LLM behavior, Flutter/device E2E, and PRD performance thresholds remain unverified. CI also does not run live provider calls or Flutter checks.
- No CI build was triggered remotely; the current workflow was reproduced locally on PostgreSQL 16 with Python 3.14.8.

## Overall

The updated automated backend checks and offline live-server smoke all pass locally. The offline eval meets its documented score target but has three known case-level mismatches. Real provider/audio acceptance still requires a separate live-provider test run.
