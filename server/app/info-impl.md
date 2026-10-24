# OJA backend: implementation as built

This describes the backend as it exists on `oja` (2026-10-24, after Phase 4). [info.md](info.md) is the original scaffold plan; this file is the current state. Requirements: [final-prd.md](../../final-prd.md). Client contract: [FRONTEND_HANDOFF.md](../../FRONTEND_HANDOFF.md). Open work: [IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md), [TODO.txt](../TODO.txt). Rules ported from the earlier parallel implementation, with their PRD checks: [BUSINESS_REQUIREMENTS.txt](../BUSINESS_REQUIREMENTS.txt).

Stack: Python 3.12+, FastAPI, SQLAlchemy 2 (ORM only), PostgreSQL, Alembic, pydantic-settings. Tests: `unittest`.

## 1. Design rules the code follows

1. **Figures come from code and the database.** The model never produces an amount, total, balance, stock level, ranking or date. It quotes phrases (`amount_text`, `due_text`); code parses them (`shared/naira.py`, `ledger/services.py:resolve_due_date`).
2. **Derived, never stored:** customer balances (sum of credit sales minus payments), quantity on hand (sum of stock movements), Home profit and loss.
3. **One transaction per workflow.** Orchestrators commit once; on any error they roll back, so nothing is half-saved (NFR-3).
4. **Every trader query is scoped by `trader_id`.** A token never reaches another trader's data.
5. **Settings only from `.env`** through `shared/env.py`; no defaults in code.
6. **Errors have one shape:** `{"error": {"code", "message"}}` (`shared/errors.py`), including 422 validation errors.

## 2. Slice layout

Each feature is a folder under `app/` (vertical slice). Files and their jobs:

| File | Job |
| --- | --- |
| `models.py` | SQLAlchemy tables the slice owns (or a comment saying it owns none) |
| `repositories/*.py` | Every database query, as classes on `BaseRepository` (commit, rollback, refresh) |
| `services.py` | Pure functions: no database, no HTTP |
| `orchestrator.py` | Workflows (one class); gets repositories and other dependencies injected; owns the transaction |
| `schemas.py` | Pydantic request and response models |
| `router.py` | FastAPI routes; builds the orchestrator with `Depends` |
| `dependencies.py` | Repository factories, so other slices can reuse them without importing routers |
| `index.py` | Empty scaffold, except `demo/index.py` (the seed command) |

All repositories in one request share one database session (FastAPI caches `get_db` per request), so a commit through any of them commits the whole unit of work.

Cross-slice use goes through repositories or orchestrators, never another slice's router internals. The only shared router dependency is `onboarding.router.get_current_trader` (the session-token check).

## 3. Slices

### onboarding: traders, sessions, login

- **Endpoints:** `POST /onboarding`, `POST /auth/login`, `POST /auth/logout`, `POST /auth/change-pin`, `WS /ws`.
- **Tables:** `locations` (seeded list of markets/areas with coordinates), `traders`, `sessions`.
- **Onboarding:** name, phone (unique, 409 `phone_taken`), business name, sector (free text), `location_name` (must match a seeded location ignoring case, 422 `unknown_location`; coordinates are copied from it), optional `items[]` (each becomes an inventory item, with an `opening` stock movement if `opening_quantity` is set), optional `pin`. Everything, including the session, is one transaction. Returns the plain session token once.
- **Sessions:** random token, stored as a SHA-256 hash; expire after `SESSION_TOKEN_TTL_DAYS`. Sessions created before expiry existed expire `created_at + TTL`, computed on read (no write during auth). Logout revokes only the current session and closes its WebSocket connections.
- **PIN (optional):** 4 to 6 digits, scrypt-hashed. Login gives the same error and takes the same time for a wrong phone, a trader without a PIN, or a wrong PIN (a dummy hash is checked). `AUTH_MAX_FAILED_LOGINS` wrong PINs in a row lock login for `AUTH_LOCK_MINUTES` (429 `account_locked`). Change PIN needs the current PIN once one exists.
- **WebSocket `/ws?token=`:** authenticates with a short-lived database session (`get_session_factory`) that is closed before the socket listens, so an open socket holds no database connection. Bad tokens close with 4401. Text `ping` gets `pong`.

### profile

- **Endpoints:** `GET /profile`, `PATCH /profile` (name, business name, sector, location; anything else is 422). A new location also updates the coordinates. Owns no tables; uses onboarding's repositories. Publishes `profile_updated`.

### ledger: messages and entries

- **Endpoints:** `POST /messages` (JSON text, or multipart voice: `audio` + `client_message_id`), `GET /entries` (`period`, `type`, `limit`, `offset`; newest first).
- **Tables:** `entries`, `entry_edits` (correction audit: old and new values as JSON), `pending_clarifications` (one per trader), `processed_messages` (dedupe key: trader + `client_message_id`, with the original reply).
- **Message flow** (`LedgerOrchestrator`):
  1. A `client_message_id` already processed returns the stored reply unchanged (NFR-5).
  2. Voice: allow-listed audio type (else 415), size limit (413), transcribe through `Infrastructure/SST`; failure is 502 and nothing is recorded, so the same id can be resent. The transcript becomes `raw_text`.
  3. If a "Do you mean X?" or "Just to confirm ...?" question is pending and the reply is yes/no (English or Pidgin, matched in code), it is answered without a model call.
  4. Otherwise the AI slice interprets the message (or the offline rules in `DEMO_MODE`). Invalid model output is retried once; a second failure asks the trader to repeat. A provider error is 503 `ai_unavailable` and nothing is recorded.
  5. Routing: `unknown` gives a polite fallback; `correction` updates the last saved entry in place (audit row written); otherwise the fields merge into the pending entry, if any.
  6. A different, complete entry sent while a question is pending replaces the pending one.
  7. Missing type, amount or (for credit sales and payments) customer: one question, built in code ("How much did you collect for the 2.5 bags?", "Which customer is this for?"). The partial entry is held.
  8. A complete entry below `CONFIDENCE_THRESHOLD` is confirmed first, unless the trader was answering our own question.
  9. The customer is resolved (see below), the entry saved, the stock effect applied, the pending row removed, the message recorded as processed: one commit.
  10. After the commit: `entry_saved` or `entry_updated`, and `inventory_changed` for every item whose stock movement changed (including the old item when a correction moves it).
- **Customer resolution:** an alias found in the message text first; several matches are narrowed by the exact name, else "Do you mean A or B?". Then the exact canonical name. Then the model matches the name against the trader's customers and aliases: at or above `CUSTOMER_MATCH_LINK_CONFIDENCE` it links and saves the alias; at or above `CUSTOMER_MATCH_CONFIRM_CONFIDENCE` it asks "Do you mean X?" (yes links and saves the alias; no creates a new customer). Below that, a new customer is created, with its own name as an alias. A name the model returns that is not in the list is ignored. Without a provider, an offline guess from a distinctive word of a name is used, always confirmed.
- **Stock effect:** at most one movement per entry, kept in line on corrections. A sale or credit sale of a stocked item moves stock out; an expense on a stocked item is a restock. The entry takes the item's unit when it gives none. Not moved, but saved and flagged in `entries.stock_warning`: a sale larger than the stock on hand (`check_stock`), a different unit (`check_stock`), an item not in inventory (`not_in_inventory`). Item and unit names compare with `shared/matching.py:match_key` (case, spaces and plural endings ignored).
- **Due dates:** credit sales only. "tomorrow"/"tmrw" +1 day, "next tomorrow" +2, "next week" +7, a weekday name its next occurrence, against the Lagos date.
- **Confirmation line:** built from saved fields ("Saved: credit sale to Mama Ngozi for ₦60,000 due Fri 30 Oct.").

### ai: interpretation only

- No endpoints, no tables. `AIOrchestrator` is injected into ledger, ask and suggestions.
- **Interpretation:** the model returns `intent` (entry, correction, unknown), type, item, quantity, unit, `amount_text`, customer, `due_text`, confidence, question. Unknown keys are dropped; there is no amount figure and no stock action in the schema.
- **Other calls:** customer match (name + confidence), `/ask` intent routing (whitelisted intent, customer and item must be in the trader's lists), restock reason wording (light Pidgin mixed with simple English, numbers kept as given).
- **`DEMO_MODE=true`:** no provider is ever called. Messages are read by rules in `ai/services.py` (type keywords, quantities with Nigerian units, amount phrases, known customers and nicknames, due phrases, pending answers, corrections). Customer matching uses the offline guess; `/ask` uses keyword routing only; reasons use the template. With `DEMO_MODE=false`, a provider failure is reported (503), never silently replaced.

### customers

- **Endpoint:** `GET /customers`: id, canonical name, aliases (other than the name itself), signed `balance_ngn` (negative = overpaid), `overdue` (still owes and a credit sale is past its due date).
- **Tables:** `customers`, `customer_aliases`. Balances come from one grouped query over entries.

### inventory

- **Endpoints:** `GET /inventory`, `POST /inventory` (name unique per trader by `match_key`, 409 `item_exists`), `PATCH /inventory/{id}` (details only; quantity cannot be sent), `POST /inventory/{id}/stock` (`opening` and `restock` positive, `adjustment` either sign, never below zero: 409 `negative_stock`; `sale` is rejected, sales come from the ledger).
- **Tables:** `inventory_items`, `stock_movements`. Quantity on hand and `low_stock` (at or below the reorder level) are derived. Publishes `inventory_changed`.

### home

- **Endpoint:** `GET /home?period=today|7d|30d` (periods start at Lagos midnight). Revenue = sales + credit sales; expenses; profit = revenue minus expenses (may be negative; payments are not revenue); total owed = sum of positive balances; items logged; low-stock items each with `top_suggestion` (first supplier for the reorder quantity, template reason, no model call; null without a reorder quantity); the 10 newest entries.

### suggestions: restock

- **Endpoint:** `GET /suggestions?item=&quantity=`; quantity defaults to the item's reorder quantity, else 422 `quantity_required`. Labelled "Demo data".
- **Tables:** `suppliers`, `supplier_offers`, `supplier_reviews` (synthetic, seeded).
- **Ranking** (`suggestions/services.py`, deterministic): five factors with weights from `.env`: distance (haversine from the trader's coordinates; score halves at `SUGGESTION_DISTANCE_HALF_KM`), average rating, quality grade (scores per grade from `.env`), cost (cheapest price / price), quantity available against quantity needed. Suppliers that can fill the quantity always rank first; ties break on distance, then id. Improving one factor never lowers a supplier's rank (tested). Top 3 returned.
- **Reasons:** worded by the model; the fallback template quotes the two strongest factors in Pidgin, with real figures ("Recommended: e dey 1.3 km away, na ₦40,000 per bag.").

### ask

- **Endpoint:** `POST /ask {question}` returns `{intent, answer, customers|sales_ngn|stock|suggestions}`. Keyword routing (English and Pidgin) first, then the model's whitelisted intent. Intents: `who_owes` (largest first, overdue marked, total), `customer_balance`, `today_total` (sales + credit sales since Lagos midnight), `stock_level`, `restock_suggestion` (same suppliers and order as `/suggestions`; asks "How many ...?" when there is no reorder quantity), `unknown`. Every figure in `answer` comes from the database.

### consent: the lender agent

- **Endpoints:** `POST /access-requests` (open; `trader_phone`, agent name, purpose, scopes from `sales_total`, `active_days`, `total_owed`; returns a one-time `claim_secret`), `GET /access-requests/{id}/status` (header `X-Claim-Secret`; the access token is returned exactly once after approval), `GET /access-requests?status=` (trader; includes a ready prompt and the last 20 log rows), `POST /access-requests/{id}/approve {approve}`, `DELETE /access/{id}`, `GET /agent/summary` (agent bearer token).
- **Tables:** `access_requests` (with `claim_hash`, `expires_at`), `access_tokens` (hashed, one per request), `access_log` (request id empty for unknown tokens).
- **Summary:** last 30 days, approved scopes only: sales total, distinct active Lagos days, total owed. Never names, raw text, entry IDs, phone or location (tested). Missing / unknown / expired / revoked token: 401 / 401 / 401 / 403. Every agent call and decision is logged, failed ones too.
- **Events:** `access_requested`, `access_decided`, `access_revoked`, `access_log`.

### demo

- **Endpoints:** `POST /demo/reset` (deletes every trader and their data; keeps locations and suppliers), `POST /demo/seed` (demo trader Tolu Adeyemi in Mushin, PIN 1234, rice/beans/garri/oil with opening stock and garri below its reorder level, customers Mama Ngozi, Mr Bayo, Aunty Funke and Iya Sade with nicknames; returns a fresh session token; safe to run twice). Both return 403 `demo_controls_disabled` unless `DEMO_CONTROLS_ENABLED=true`. The dashboard uses the demo trader's token (no endpoint is readable without a token).
- **Command:** `python -m app.demo.index` seeds 8 locations and 6 synthetic suppliers (24 offers, 18 reviews); safe to rerun.

## 4. Shared infrastructure (`app/shared/`)

| Module | What it does |
| --- | --- |
| `env.py` | `Settings`: every key required, read from the root `.env` |
| `errors.py` | `AppError(status, code, message)` and the handlers that give every error the one shape |
| `periods.py` | `LAGOS`, `period_start` (today / 7d / 30d from Lagos midnight), `as_utc` for naive SQLite datetimes |
| `naira.py` | `parse_naira_amount`: "ten k", "2.5k", "₦60,000", "two and a half k", "1.2m" → Decimal |
| `matching.py` | `match_key` for item and unit names |
| `types.py` | `Money`, `Quantity`: exact Decimals sent as JSON numbers |
| `Infrastructure/db/` | `Base` (naming convention), `session.py` (`engine`, `SessionLocal`, `get_db`, `get_session_factory`), `base_repository.py`, Alembic in `alembic/` |
| `Infrastructure/llm/client.py` | `LLMClient`: OpenAI-compatible chat, JSON mode, timeout, `max_tokens`, in-memory cache of identical requests, call counter, one retry on HTTP 429 (waits `Retry-After`, capped) |
| `Infrastructure/SST/client.py` | OpenAI-compatible transcription (local whisper.cpp server, or an online provider by `.env`); audio type allow-list |
| `Infrastructure/realtime/hub.py` | WebSocket hub: per-trader sockets with their session and expiry; `publish` and `end_session` are safe from any thread; events only after commit; expired sockets close with 4401; one uvicorn worker only |

`main.py` mounts every router, the error handlers, `GET /health`, and CORS (only `CORS_ORIGINS`, no cookies).

## 5. Data model and migrations

| Owner | Tables |
| --- | --- |
| onboarding | `locations`, `traders` (incl. `pin_hash`, `failed_logins`, `locked_until`), `sessions` (incl. `expires_at`) |
| customers | `customers`, `customer_aliases` |
| inventory | `inventory_items`, `stock_movements` |
| ledger | `entries` (incl. `stock_warning`), `entry_edits`, `pending_clarifications`, `processed_messages` |
| consent | `access_requests`, `access_tokens`, `access_log` |
| suggestions | `suppliers`, `supplier_offers`, `supplier_reviews` |

Money is `Numeric(14,2)`, quantities `Numeric(14,3)`, timestamps timezone-aware with database defaults, JSON columns are JSONB on PostgreSQL. Migrations (`alembic.ini` at the repo root; `env.py` imports every slice's models): `645c930b9cc6` initial schema → `c3819b46ad50` entry stock warning → `5b14d59c5953` consent tables → `355529bd3baa` PIN login and session expiry. Tables change only through Alembic; `alembic check` must report no drift.

## 6. Configuration (`.env`, see `.env.example`)

| Group | Keys |
| --- | --- |
| Database | `DATABASE_URL`, `DB_ECHO`, `DB_POOL_SIZE`, `DB_MAX_OVERFLOW` |
| LLM | `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_TIMEOUT_SECONDS`, `LLM_MAX_TOKENS`, `LLM_RATE_LIMIT_DEFAULT_WAIT_SECONDS`, `LLM_RATE_LIMIT_MAX_WAIT_SECONDS` |
| Speech-to-text | `STT_BASE_URL`, `STT_INFERENCE_PATH`, `STT_API_KEY`, `STT_MODEL`, `STT_TIMEOUT_SECONDS`, `STT_MAX_UPLOAD_MB` |
| Ledger | `CONFIDENCE_THRESHOLD`, `CUSTOMER_MATCH_LINK_CONFIDENCE`, `CUSTOMER_MATCH_CONFIRM_CONFIDENCE` |
| Suggestions | `SUGGESTION_WEIGHT_DISTANCE`, `_RATING`, `_QUALITY`, `_COST`, `_QUANTITY`, `SUGGESTION_DISTANCE_HALF_KM`, `SUGGESTION_QUALITY_SCORE_A`, `_B`, `_C` |
| Demo and access | `DEMO_MODE`, `DEMO_CONTROLS_ENABLED`, `SESSION_TOKEN_TTL_DAYS`, `AUTH_MAX_FAILED_LOGINS`, `AUTH_LOCK_MINUTES`, `ACCESS_TOKEN_TTL_MINUTES`, `CORS_ORIGINS` |

## 7. Running, testing, evaluating

- **Make targets** (repo root): `setup`, `migrate`, `seed`, `dev` (uvicorn, one worker), `test`, `eval`, `eval-live`.
- **Tests:** `server/tests/`, 165 tests. `tests/support.py` runs the real app on a fresh in-memory SQLite database per test with a fake LLM and a fake transcriber (no key, no network); `TEST_DATABASE_URL` runs them on a throwaway PostgreSQL. Covers every endpoint, the PRD acceptance examples, the 8-step golden path offline with zero provider calls, consent privacy, WebSocket delivery and closing.
- **Eval harness** (`server/eval/`): 40 Pidgin/English cases (10 hard) through `POST /messages` on a fresh database with the demo trader. Offline (rules): 37 of 40. `--live` uses the LLM in `.env`. Results go to `server/eval/results.json` (gitignored). The cases still need a second reviewer (FR-S19).
- **CI:** `.github/workflows/backend-tests.yml` runs the tests on Python 3.12 for pushes to `oja` that touch the backend.

## 8. Known limits and open items

- No per-message structured log yet (task 3.7, NFR-10).
- Item matching handles case, spaces and plurals only; synonyms ("palm oil" vs "oil") and item aliases are open (`TODO.txt`).
- Sector is free text (fixed list skipped, task 4.5).
- The Flutter client does not call the API yet; there is no judges' dashboard page (endpoints only).
- The WebSocket hub is in-process: run a single uvicorn worker.
- `POST /access-requests` with an unregistered phone returns 404, which tells a caller whether a number is registered.
- The local whisper.cpp server needs `--convert` (ffmpeg) for M4A uploads.
- The eval's live score has not been measured (no `LLM_API_KEY` set).
