# OJA

Speak or type in Pidgin or English, and your books write themselves. OJA is a Flutter app for Lagos foodstuff traders (rice, beans, garri, oil) with a FastAPI backend. Built for T.I.C Hackathon 3.0.

Design rule: the AI only interprets messages and phrases explanations. Totals, debts, profit, stock levels and supplier rankings always come from the database and code.

Full requirements: [final-prd.md](final-prd.md). Agent rules: [AGENTS.md](AGENTS.md). Client contract: [FRONTEND_HANDOFF.md](FRONTEND_HANDOFF.md).

## Status

The new backend in `server/` is being built. Only the database boilerplate exists so far (SQLAlchemy base, engine and session). The feature folders are empty placeholders. No endpoint is implemented in `server/` yet.

`backend.py/`, `eval/` and `render.yaml` are the earlier MerchantPal prototype (SQLite, single merchant). They are legacy and will be replaced or removed as the OJA slices land.

## Stack

- Backend: Python 3.12+, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL.
- Client: Flutter (Android), in `client/`. Not started.
- Dashboard for judges: plain HTML. Not started.

The PRD (decision D2) still says SQLite. The team chose PostgreSQL, so the PRD needs updating.

## Backend layout (vertical slices)

Each feature is a folder under `server/app/` with an `index.py` entry point.

| Folder | Covers |
| --- | --- |
| `ledger` | `/messages`, `/entries`, clarifications, corrections, shorthand, dedupe |
| `ai` | Extraction, matching, intent routing, wording, LLM and speech wrapper |
| `customers` | Customers, aliases, debts, `/customers` |
| `ask` | `/ask` intent whitelist and parameterised queries |
| `consent` | Access requests, approve and revoke, `/agent/summary`, access log |
| `onboarding` | `/onboarding` and session tokens |
| `profile` | `/profile` |
| `inventory` | Items and stock movements |
| `home` | `/home` profit and loss |
| `suggestions` | Supplier data, ranking, `/suggestions` |
| `demo` | Seed and reset |
| `shared` | `env.py` settings and `Infrastructure/` (`db`, `llm`, `SST`) |

## Setup

Dependencies are managed with Poetry (`pyproject.toml`).

```sh
poetry install
cp .env.example .env   # then fill in real values
```

Settings are read from the root `.env` by `server/app/shared/env.py`. Nothing is hardcoded in code, and a missing value fails at startup.

| Variable | Meaning |
| --- | --- |
| `DATABASE_URL` | SQLAlchemy URL, for example `postgresql+psycopg://user:password@localhost:5432/oja` |
| `DB_ECHO` | `true` logs SQL |
| `DB_POOL_SIZE` | Connection pool size |
| `DB_MAX_OVERFLOW` | Extra connections beyond the pool |

LLM variables (`OPENAI_API_KEY`, `OPENAI_BASE_URL`, `MERCHANTPAL_MODEL`) are in `.env.example` for the AI slice. Never commit `.env`.

## Working agreement

Small commits (10 files max), one branch per task, never work on `main`, no new dependencies without asking. See [AGENTS.md](AGENTS.md).
