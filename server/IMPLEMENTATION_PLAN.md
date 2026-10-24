# OJA backend: implementation plan

Status as of 2026-10-24, branch `oja`. Phases 1 to 4 are done for the demo; what is left is listed under "Open work". Source of truth: [final-prd.md](../final-prd.md). The system as built: [app/info-impl.md](app/info-impl.md). The original scaffold plan: [app/info.md](app/info.md).

## Where we are

**Live and tested** (173 tests, CI on every push to `oja`; the 8-step golden path runs end to end, also offline with `DEMO_MODE`):

- onboarding (main items and opening stock, optional PIN), login, logout, session expiry, profile
- messages (text and voice): dedupe, clarify, correct, confidence check, "Do you mean ...?" for customers and items, due dates, stock effects and warnings
- entries, customers (aliases, signed balance, overdue), inventory (read and write), Home (profit and loss, restock card, recent entries)
- restock suggestions, `/ask`, consent and the lender agent summary
- WebSocket change events, demo reset and seed, `DEMO_MODE`, CORS, LLM rate-limit retry
- eval harness (offline 37 of 40), Makefile, Alembic migrations up to `355529bd3baa`

**Client:** `client/` (Flutter) was not changed by the backend work. Its API integration should start from the contract below.

## For the Flutter developer: what to build against

- **The contract is [FRONTEND_HANDOFF.md](../FRONTEND_HANDOFF.md)**: every endpoint, request and response shape, error code, the message statuses and assistant questions, and the WebSocket events. The live schema is at `/docs` when the server runs. Older notes (the prototype `backend.py/`, earlier drafts of the handoff, the teammate's code at `1a81088`) are not the contract.
- **Run a local backend:** `make setup`, `make migrate`, `make seed`, `make dev`. For a ready trader with stock and customers, set `DEMO_CONTROLS_ENABLED=true` and call `POST /demo/seed` (returns a token; the demo trader's PIN is 1234). For no model calls at all, set `DEMO_MODE=true`.
- **Auth:** `Authorization: Bearer <token>` from `POST /onboarding` or `POST /auth/login`. A 401 means back to onboarding or login.
- **Messages:** send a new `client_message_id` per message and reuse it on retry. Show `message`; when `status` is `clarify`, the trader's next message is the answer (yes/no is understood for "Do you mean ...?" and "Just to confirm ...?").
- **Live updates:** connect to `/ws?token=<session token>` and refetch on an event; the socket closes with 4401 when the session ends.
- **Never compute figures in the app:** totals, balances, stock and rankings always come from the API.

## Working rules (from AGENTS.md)

- One branch per task, never `main`. Small commits (the team agreed 10 to 12 files at most). No new dependencies without asking.
- Every task: state assumptions, list changes, log the action in `FRONTEND_HANDOFF.md`.
- Every new or changed table ships with an Alembic migration. Never edit a merged migration.
- Settings come from `.env` through `app/shared/env.py`, with no hardcoded values. Add new keys to `.env.example`.
- Figures (totals, balances, stock, rankings) come from code and the database, never from model output (PRD design rule).
- Rules ported from the earlier implementation are in [BUSINESS_REQUIREMENTS.txt](BUSINESS_REQUIREMENTS.txt); use only those marked VALIDATED.

## Decisions (all resolved)

| ID | Decision | Outcome |
|---|---|---|
| D1 | Login and session expiry | Optional PIN (at onboarding or via `/auth/change-pin`); login works once a PIN exists; sessions expire after `SESSION_TOKEN_TTL_DAYS` (older sessions: from their creation time) |
| D2 | Real-time updates | Authenticated WebSocket at `/ws`; no Flutter changes or dashboard page in this scope |
| D3 | Where voice is transcribed | Either: the app may send on-device text, or upload audio to the server's speech-to-text (whisper.cpp with `--convert`, or an online provider via `.env`) |
| D4 | Dashboard access | The demo trader's token from `POST /demo/seed`; no endpoint is readable without a token |
| D5 | Fixed sector list | Skipped for the demo; sector stays free text |
| D6 | Item name matching | Name match ignoring case, spaces and plurals, then the model against the trader's inventory (sure: link; unsure: "Do you mean oil?"; otherwise not in inventory). A different unit is flagged `check_stock`. Suggestions match supplier items by name only |

## Task overview

| ID | Task | PRD | Status |
|---|---|---|---|
| **Phase 1: Clean up and stabilise** | | | |
| 1.1 | Remove the teammate's dead server code | — | Done |
| 1.2 | Restore our `session.py` | NFR-3 | Done |
| 1.3 | Tidy `env.py`, `.env`, `.env.example` | NFR-7 | Done |
| 1.4 | Rewrite `FRONTEND_HANDOFF.md` and the README to our contract | — | Done |
| 1.5 | Turn the throwaway end-to-end scripts into repo tests | NFR-11 | Done |
| **Phase 2: Golden path** | | | |
| 2.1 | Inventory write endpoints | FR-S23, S24 | Done |
| 2.2 | Main items and opening stock at onboarding | FR-S21 | Done |
| 2.3 | Customer name confirmation and alias creation | FR-S9 | Done |
| 2.4 | `/ask` slice | FR-S11, S32 | Done |
| 2.5 | Due dates computed in code, overdue flags | FR-S12 | Done |
| 2.6 | Consent slice | FR-S13 to S17 | Done |
| 2.7 | Home restock card and recent entries | FR-S32, C13 | Done |
| **Phase 3: Demo safety and NFRs** | | | |
| 3.1 | `DEMO_MODE`: offline rule-based interpretation | NFR-4 | Done |
| 3.2 | LLM rate-limit retry | NFR-8 | Done |
| 3.3 | Demo reset and seed endpoints (no dashboard page, per D4) | FR-C10 | Done |
| 3.4 | CORS | NFR-7 | Done |
| 3.5 | Session expiry, logout, optional PIN | NFR-7 | Done |
| 3.6 | Real-time updates (WebSocket) | FR-C13, C6 | Done |
| 3.7 | Structured log per message | NFR-10 | **Open** |
| 3.8 | Voice path finalised | FR-S2 | Partly: documented; the 5 Pidgin clip test needs real audio |
| **Phase 4: Quality and delivery** | | | |
| 4.1 | Eval harness for the server pipeline | FR-S18 to S20 | Done (cases need a second reviewer; live score not yet measured) |
| 4.2 | Makefile entry points | NFR-11 | Done |
| 4.3 | CI pipeline (light: backend tests on pushes to `oja`) | T-05 | Done |
| 4.4 | Item matching | FR-S25, S30 | Done |
| 4.5 | Fixed sector list | D7 | Skipped (D5) |

## Open work

- 3.7: one structured log line per message (NFR-10).
- 3.8: test 5 recorded Pidgin voice clips on the chosen speech-to-text.
- 4.1: a teammate reviews `server/eval/cases.json`; run `make eval-live` once `LLM_API_KEY` is set.
- Apply and check the migrations on the shared PostgreSQL (`make migrate`, `alembic check`).
- Flutter: integrate the client with the API (contract above).

The sections below are the original task briefs, kept as a record.

---

## Phase 1: Clean up and stabilise

**Status: done (2026-10-24).** Dead code removed and its business rules kept in `BUSINESS_REQUIREMENTS.txt`. `session.py` restored. Settings tidied (30 required keys). Docs rewritten. 58 repo tests pass on SQLite and on PostgreSQL.

### 1.1 Remove the teammate's dead server code

**Why:** this is a parallel implementation that crashes on import. For example, `shared/auth.py` imports `SessionToken` and PIN fields that don't exist in our models. It confuses which code is real and risks being mounted by mistake.
**Scope:** delete these files. They stay readable at `1a81088`.
- The `index.py` files of `ai`, `ask`, `consent`, `customers`, `home`, `inventory`, `ledger`, `onboarding` and `suggestions`. Leave them empty, as originally scaffolded, except `demo/index.py`, which is our seed command.
- `consent/models.py`, which is rebuilt in 2.6.
- `shared/auth.py`, `shared/realtime.py`, `suggestions/config.py`, `suggestions/seed.py`, `demo/dashboard.html`.
- The `index.py` files under `shared/Infrastructure/llm` and `shared/Infrastructure/SST`.
- `server/pyproject.toml`, which is stale: we use `.venv` and `requirements.txt`.

**Acceptance:** `python -c "import app.main"` passes. Unit tests pass. `grep -r "app.shared.auth\|realtime\|suggestions.seed" server/app` finds nothing. Two commits, because of the 10-file limit.

### 1.2 Restore our `session.py`

**Why:** the merged version imports the consent models and adds `initialize_database()` with `create_all`, which bypasses Alembic. It also adds a SQLite branch we don't use.
**Scope:** `shared/Infrastructure/db/session.py` keeps only `engine`, `SessionLocal` and `get_db`. Keep `session_scope()` only if a task needs it. Table registration lives in `alembic/env.py`.
**Acceptance:** `alembic check` shows no drift, and the app and tests pass.

### 1.3 Tidy `env.py`, `.env` and `.env.example`

**Why:** `LLM_TIMEOUT_SECONDS` is defined twice. Nine of the teammate's settings have hardcoded defaults, which breaks the no-hardcoding rule. Some of them will be needed later.
**Scope:**
- Remove `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OJA_MODEL` and `OJA_STT_MODEL`, which are covered by `LLM_*` and `STT_*`. Remove the duplicate `LLM_TIMEOUT_SECONDS`.
- Keep `DEMO_MODE`, `DEMO_CONTROLS_ENABLED`, `SESSION_TOKEN_TTL_DAYS`, `ACCESS_TOKEN_TTL_MINUTES` and `CORS_ORIGINS` as required `Field(default=...)` values, so each is read from `.env`.
- In `.env.example`, group the keys by area with one comment each. Keep the old `OPENAI_*` keys under a "backend.py prototype" heading.

**Acceptance:** the app starts with `.env` and fails clearly if a key is missing. `.env.example` lists every key.

### 1.4 Rewrite `FRONTEND_HANDOFF.md` and the README to our contract

**Why:** both now describe the teammate's API: base64 voice in JSON, PIN login, `confirmation`, `/ask` and consent shapes. The client team would build against the wrong contract.
**Scope:**
- Document the live endpoints with request, response and error examples. Reuse the captured examples from the testing guide.
- Mark planned endpoints (ask, consent, inventory writes) as planned.
- Keep the agent action log.
- In the README: setup with `.venv`, `alembic upgrade head`, the seed command, the run command, and `backend.py/` described as a prototype.

**Acceptance:** every request in the doc runs against the live server as written.

### 1.5 Turn the throwaway end-to-end scripts into repo tests

**Why:** only 2 unit-test files are in the repo. The workflow checks (dedupe, clarify, correct, atomic rollback, Home P&L, voice errors, suggestions) were throwaway scripts.
**Scope:**
- Add `server/tests/support.py` with an in-memory SQLite app fixture, a fake LLM client and a fake transcriber.
- Add test modules per slice: onboarding and profile, ledger workflows, messages API, home, suggestions API.
- Optionally run against Postgres when `TEST_DATABASE_URL` is set.
- Use `unittest`, so no new dependency.

**Acceptance:** `python -m unittest discover -s tests -t .` covers every endpoint and every PRD acceptance example implemented so far, with no API key and no network.

## Phase 2: Golden path

**Status: done (2026-10-24).** All seven tasks built on the decisions recorded in `BUSINESS_REQUIREMENTS.txt` (oversell saves without moving stock; a complete new entry replaces a pending one; consent by phone + claim secret; due dates quoted by the model and resolved in code; no default restock quantity; stock warning stored on the entry; signed customer balance; reasons that quote the facts). Migrations `c3819b46ad50` and `5b14d59c5953`. 114 tests pass on SQLite and PostgreSQL.

### 2.1 Inventory write endpoints (FR-S23, S24)

**Scope:**
- `POST /inventory` adds an item.
- `PATCH /inventory/{id}` edits details, and never quantity.
- `POST /inventory/{id}/stock` records an opening, restock or adjustment movement. A negative change is allowed only for an adjustment.
- Add repository methods, orchestrator workflows and schemas. Reference: `git show 1a81088:server/app/inventory/index.py`.

**Acceptance:** opening 10 + restock 5 gives 15, then an adjustment of −2 gives 13. A PATCH never changes quantity on hand. One trader can't reach another trader's items (404).

### 2.2 Main items and opening stock at onboarding (FR-S21)

**Scope:** `OnboardingRequest.items[]` takes name, unit, optional opening quantity, reorder level and reorder quantity. Onboarding creates the inventory items and opening movements in the same transaction as the trader and session, using the inventory repository.
**Acceptance:** onboarding with 2 items gives `/inventory` showing both, with their opening quantities. If any part fails, nothing is saved.

### 2.3 Customer name confirmation and alias creation (FR-S9)

**Why:** alias lookup works, but nothing creates aliases, so "the rice woman" never resolves. Golden step 5 fails.
**Scope:**
- When neither alias nor canonical name matches and the trader already has customers, ask the AI slice to match the mention against the customer list.
- If the match is unsure, hold a clarification asking "Do you mean Mama Ngozi?".
- A yes saves the mention as an alias and completes the entry. A no creates a new customer.
- Yes/no detection runs in code. Reference: the `YES_PATTERN`/`NO_PATTERN` constants and `_resolve_customer` in `git show 1a81088:server/app/ledger/index.py`, plus `match_customer` in `…/llm/index.py`.

**Acceptance:** "The rice woman don pay thirty k" asks "Do you mean Mama Ngozi?", and "yes" links the payment and saves the alias. The next message using "the rice woman" resolves with no question.

### 2.4 `/ask` slice (FR-S11, S32)

**Scope:**
- New `ask` slice with the five layers. `POST /ask {question}` returns `{intent, answer, data}`.
- Intents on a whitelist: `who_owes`, `customer_balance`, `today_total`, `stock_level`, `restock_suggestion`, `unknown`.
- Keyword routing first, then an AI intent pick that returns an intent and parameters only, never SQL.
- Answers come from the customers, ledger, inventory and suggestions orchestrators.
- `today_total` uses Lagos time.
- Reference: `git show 1a81088:server/app/ask/index.py`.

**Acceptance:**
- "Who owes me?" lists balances from the database.
- "Where I fit buy rice?" returns the same suppliers in the same order as `GET /suggestions`.
- An unknown question returns a fallback.
- Model output can't change any figure (test with a fake LLM returning numbers).

### 2.5 Due dates computed in code, overdue flags (FR-S12)

**Scope:**
- The AI quotes the due phrase (`due_text`: "Friday", "next week"), and code resolves it against the trader's Lagos date. This matches the approach already used for `amount_text`.
- `/customers` and `who_owes` flag overdue customers: those with an open credit sale past its due date.
- Reference: `_due_date` in `git show 1a81088:server/app/shared/Infrastructure/llm/index.py`.

**Acceptance:** on a Wednesday, "she go pay Friday" saves the coming Friday's date. After that date the customer shows `overdue: true`.

### 2.6 Consent slice (FR-S13 to S17)

**Scope (two sessions):**
- **Models and migration:** `access_requests`, `access_tokens`, `access_log`, plus an Alembic migration. Add the import to `alembic/env.py`.
- **Endpoints:**
  - `POST /access-requests` (open, returns no data) and `GET /access-requests?status=`.
  - `POST /access-requests/{id}/approve {approve}`, which issues a token with an expiry from `ACCESS_TOKEN_TTL_MINUTES`.
  - `DELETE /access/{id}`.
  - `GET /agent/summary`, which returns totals only: sales total, active days, total owed.
- **Port the teammate's agent flow:** the agent gets a one-time claim secret, polls `GET /access-requests/{id}/status`, and collects the token exactly once. Tokens are stored hashed.
- **Logging:** every agent call writes an access-log row.
- Reference: `git show 1a81088:server/app/consent/index.py` and `…/consent/models.py`.

**Acceptance:**
- A request missing purpose or scopes returns 422. A rejected request issues no token.
- Valid, expired, revoked and missing tokens each return the right status and write a log row.
- A test asserts that no customer name, raw text, entry ID, phone or location ever appears in `/agent/summary`.

### 2.7 Home restock card and recent entries (FR-S32, C13)

**Scope:** each `low_stock_items[]` entry carries `top_suggestion`: the first result from `SuggestionOrchestrator`, with no model call on Home, so it stays fast. Add `recent_entries` (the last 10).
**Acceptance:** with rice at or below its reorder level, Home shows the same top supplier as `GET /suggestions?item=rice`.

## Phase 3: Demo safety and NFRs

### 3.1 `DEMO_MODE`: offline rule-based interpretation (NFR-4)

**Scope:**
- When `DEMO_MODE=true` or the LLM is unreachable, the AI slice returns an `Interpretation` from a rule-based extractor covering the golden-path phrasings.
- Suggestion reasons fall back to the template.
- Reference: `_demo_extract` and `_demo_correction` in `git show 1a81088:server/app/shared/Infrastructure/llm/index.py`.

**Acceptance:** the 8-step golden path runs end to end with no network.

### 3.2 LLM rate-limit retry (NFR-8)

**Scope:** in `LLMClient`, one retry on HTTP 429, honouring `Retry-After` up to 3 seconds. It must not stack with the validation retry beyond 2 provider calls per message.
**Acceptance:** a fake 429 then 200 succeeds, and a double 429 returns 503 `ai_unavailable`.

### 3.3 Demo reset and seed endpoints, judges' dashboard (FR-C6 to C11)

**Scope:**
- `POST /demo/reset` clears trader data and keeps the reference data. `POST /demo/seed` adds the demo trader, 4 to 5 customers with aliases, and starting stock.
- Both work only when `DEMO_CONTROLS_ENABLED=true`.
- Read endpoints feed the dashboard: entries with `raw_text`, customers with balances and overdue flags, access requests and log. Access follows D4.
- Serve a static dashboard page. Reference: `git show 1a81088:server/app/demo/dashboard.html`.

**Acceptance:** reset and seed each finish in under 10 seconds. The dashboard shows a new entry within 3 seconds.

### 3.4 CORS (NFR-7)

**Scope:** add `CORSMiddleware` in `main.py`, limited to the `CORS_ORIGINS` value from `.env`.
**Acceptance:** the dashboard origin is allowed and any other origin is refused.

### 3.5 Session expiry and logout, plus PIN if D1 says so

**Scope:**
- `sessions.expires_at` (migration), with the lifetime from `SESSION_TOKEN_TTL_DAYS`, and `POST /auth/logout`.
- Optional 4–6 digit PIN at onboarding or later through `POST /auth/change-pin`; `POST /auth/login` is available only after a PIN is set. Store PINs with scrypt and lock out after 5 wrong PINs. Existing sessions with no expiry get `created_at + SESSION_TOKEN_TTL_DAYS` persisted on first authentication; if that time has passed, return 401. Reference: `git show 1a81088:server/app/shared/auth.py` and `…/onboarding/index.py`.

**Acceptance:** new and legacy sessions expire on the configured schedule; an expired or logged-out token returns 401. A trader without a PIN cannot log in, but can set one from an active session.

**Status (2026-10-24):** implemented and verified. Legacy sessions without an expiry are assigned their finite expiry on first authentication; expired sessions are rejected.

### 3.6 Real-time updates (per D2)

**Scope:** add an authenticated `/ws?token=<session token>` endpoint. Reject missing, invalid, expired and revoked tokens with close code `4401`; support `ping`/`pong`; clean up disconnected clients; publish events only after the associated database commit. Event types: `entry_saved`, `entry_updated`, `inventory_changed`, `profile_updated`, `access_requested`, `access_decided`, `access_revoked`, and `access_log`. Keep the hub single-process and document the single-Uvicorn-worker requirement. REST remains the source of truth; events tell clients when to refresh. No Flutter implementation or judges' dashboard page is included in this task.

**Acceptance:** an authenticated socket receives only that trader's events, an unauthenticated socket closes with `4401`, ping receives pong, and saved ledger/inventory/profile/consent changes publish their matching events after commit. Disconnecting a client removes it from the hub. Verify transport behavior without editing Flutter.

**Status (2026-10-24):** implemented and verified with focused backend tests and direct WebSocket checks. No Flutter or dashboard-page changes.

### 3.7 Structured log per message (NFR-10)

**Scope:** one JSON log line per message with the trader ID, client message ID, input, interpretation, status, confidence, latency and LLM call count. Never log tokens.
**Acceptance:** a failed extraction can be explained from the logs alone.

### 3.8 Voice path finalised (per D3)

**Scope:** if the client transcribes on the device, document text-only use and keep server STT as optional. If the server transcribes, document `--convert` for whisper.cpp (it needs ffmpeg), or have the app record 16 kHz WAV. Test 5 Pidgin clips (PRD T-22).
**Acceptance:** an M4A or WAV recorded on the demo phone is saved with its transcript in `raw_text`.

## Phase 4: Quality and delivery

**Status: done for the demo (2026-10-24).** 4.1 eval harness: 40 drafted cases, offline score 37 of 40 (hard 7 of 10); the cases still need a second reviewer. 4.2 Makefile at the repo root. 4.3 one light GitHub Actions workflow running the backend tests on pushes to `oja` (approved). 4.4 item and unit matching ignores case, spaces and plural endings; a different unit is flagged `check_stock`. 4.5 skipped (sector stays free text).

### 4.1 Eval harness for the server pipeline (FR-S18 to S20)

**Scope:**
- Put 40 Pidgin and English sentences, with the expected entry or expected question, in `server/eval/cases.json`.
- They must cover all four entry types, shorthand, nicknames, corrections and ambiguous cases, with at least 10 hard ones.
- The runner pushes each case through the AI and ledger pipeline on a throwaway database, prints "N of 40 correct" with expected versus got, and exports JSON.
- The existing `eval/` folder targets the `backend.py` prototype. Reuse its cases where they fit.

**Acceptance:** `make eval` runs live, and CI runs it on fixtures. The target is at least 30 of 40.

### 4.2 Makefile entry points (NFR-11)

**Scope:** targets `setup`, `dev`, `migrate`, `seed`, `reset`, `check` (unit and integration tests, plus Flutter analyze and test), `eval` and `demo`.
**Acceptance:** each target works from a fresh clone, given `.env`.

### 4.3 CI pipeline (needs approval: AGENTS.md says not to edit CI config)

**Scope:** GitHub Actions with Postgres. Run migrations, tests, the eval harness on fixtures, a secret scan, and Flutter analyze. Branch protection on `main`.
**Acceptance:** a pull request is blocked on red.

### 4.4 Item matching (per D6)

**Scope:** implement the agreed option for matching items between ledger, inventory and suggestions, and for handling units.
**Acceptance:** "palm oil", "bag of rice" and singular versus plural units behave as agreed. A test covers each case.

### 4.5 Fixed sector list (per D5)

**Scope:** add a `Sector` literal in the onboarding and profile schemas.
**Acceptance:** an unknown sector returns 422.

---

## Golden path check (run after each phase)

| Step | Needs | Status now |
|---|---|---|
| 1 Onboard and choose a sector | 2.2, 4.5 | Done (fixed sector list is 4.5) |
| 2 Credit sale by voice | 3.8 | Done in code |
| 3 Clarify an ambiguous sale | — | Done |
| 4 Correct it | — | Done |
| 5 Payment against a nickname | 2.3 | Done |
| 6 Ask who owes | 2.4 | Done |
| 7 Home P&L, stock, restock suggestion | 2.1, 2.7 | Done |
| 8 Approve a lender agent, see the summary | 2.6 | Done |
