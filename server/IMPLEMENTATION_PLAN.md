# OJA backend: implementation plan (post-merge fixes)

Status as of 2026-10-24, branch `oja` at `3cc07ff`. Source of truth: [final-prd.md](../final-prd.md). Architecture: [app/info.md](app/info.md).

## Where we are

**Works today:** these slices are mounted in `server/app` and tested, including against Postgres:
- onboarding (no main items yet) and profile
- customers (aliases, balances)
- ledger (`POST /messages` text and voice, dedupe, clarify, correct, confidence gate)
- inventory (read only)
- home
- suggestions
- the demo seed command

Alembic is at `645c930b9cc6` with no drift.

**Broken or missing:**
- **Golden path:** steps 5 to 8 fail. Aliases are never created, there is no `/ask`, stock can't be managed from the app, and there is no consent.
- **Dead teammate code:** 19 files (about 2,000 lines) of a parallel implementation sit in `server/`. None of it is mounted, and it fails on import.
- **Mixed files:** `session.py` and `env.py` are part ours, part theirs.

**Client:** `client/` (Flutter) makes no API calls yet. It keeps a local ledger and uses on-device `speech_to_text`. Our API contract is therefore the one the client integrates against (see [FRONTEND_HANDOFF.md](../FRONTEND_HANDOFF.md) once task 1.4 updates it).

**Reference:** the teammate's implementation lives in git history at `1a81088`. Read any file with `git show 1a81088:<path>`. Several tasks below port ideas from it into our layers (models, repositories, services, orchestrator, router).

## Working rules (from AGENTS.md)

- One branch per task, never `main`. At most 10 files per commit. No new dependencies without asking.
- Every task: state assumptions, list changes, log the action in `FRONTEND_HANDOFF.md`.
- Every new or changed table ships with an Alembic migration. Never edit a merged migration.
- Settings come from `.env` through `app/shared/env.py`, with no hardcoded values. Add new keys to `.env.example`.
- Figures (totals, balances, stock, rankings) come from code and the database, never from model output (PRD design rule).
- Before starting a Phase 2 to 4 task, read the rules listed for it in [BUSINESS_REQUIREMENTS.txt](BUSINESS_REQUIREMENTS.txt), validate each against the PRD, record the result on its STATUS line, and only use rules marked VALIDATED.

## Decisions needed before the blocked tasks

| ID | Decision | Options | Blocks |
|---|---|---|---|
| D1 | Login with phone + PIN, plus session expiry | Port now / later / drop. PRD D7 says no password; you said earlier that login comes later | 3.5 |
| D2 | Real-time updates for the app and dashboard | Client polling (PRD) / WebSocket (teammate) / server-sent events | 3.6 |
| D3 | Where voice is transcribed | Server STT (built; whisper.cpp needs `--convert` for M4A) / client on-device STT sends text only / both | 3.8 |
| D4 | Dashboard access without a session token (PRD section 8) | Read-only demo token / enable only when `DEMO_CONTROLS_ENABLED` is set / public reads | 3.3 |
| D5 | Fixed sector list (PRD D7) | Agree the values, e.g. foodstuff, provisions, fabrics, electronics, other | 4.5 |
| D6 | Item name matching | See `server/TODO.txt` item 1 | 4.4 |

## Task overview

| ID | Task | PRD | Priority | Est. | Depends |
|---|---|---|---|---|---|
| **Phase 1: Clean up and stabilise** | | | | | |
| 1.1 | Remove the teammate's dead server code | — | Must | 20m | — |
| 1.2 | Restore our `session.py` | NFR-3 | Must | 15m | 1.1 |
| 1.3 | Tidy `env.py`, `.env`, `.env.example` | NFR-7 | Must | 30m | 1.1 |
| 1.4 | Rewrite `FRONTEND_HANDOFF.md` and the README to our contract | — | Must | 45m | 1.1 |
| 1.5 | Turn the throwaway end-to-end scripts into repo tests | NFR-11 | Must | 90m | 1.2 |
| **Phase 2: Golden path** | | | | | |
| 2.1 | Inventory write endpoints | FR-S23, S24 | Must | 60m | 1.5 |
| 2.2 | Main items and opening stock at onboarding | FR-S21 | Must | 45m | 2.1 |
| 2.3 | Customer name confirmation and alias creation | FR-S9 | Must | 90m | 1.5 |
| 2.4 | `/ask` slice | FR-S11, S32 | Must | 90m | 2.3 |
| 2.5 | Due dates computed in code, overdue flags | FR-S12 | Should | 60m | 2.4 |
| 2.6 | Consent slice | FR-S13 to S17 | Must | 2 × 90m | 1.5 |
| 2.7 | Home restock card and recent entries | FR-S32, C13 | Must | 45m | 2.1 |
| **Phase 3: Demo safety and NFRs** | | | | | |
| 3.1 | `DEMO_MODE`: offline rule-based interpretation | NFR-4 | Must | 90m | 2.4 |
| 3.2 | LLM rate-limit retry | NFR-8 | Should | 30m | — |
| 3.3 | Demo reset and seed endpoints, judges' dashboard | FR-C6 to C11 | Must | 90m | 2.6, D4 |
| 3.4 | CORS | NFR-7 | Must | 15m | 1.3 |
| 3.5 | Session expiry, logout (plus PIN if D1 says so) | NFR-7 | Should | 60m | D1 |
| 3.6 | Real-time updates | FR-C13, C6 | Should | 60m | D2 |
| 3.7 | Structured log per message | NFR-10 | Should | 45m | — |
| 3.8 | Voice path finalised | FR-S2 | Should | 30m | D3 |
| **Phase 4: Quality and delivery** | | | | | |
| 4.1 | Eval harness for the server pipeline | FR-S18 to S20 | Must | 2 × 90m | 3.1 |
| 4.2 | Makefile entry points | NFR-11 | Must | 30m | 1.5 |
| 4.3 | CI pipeline (needs approval) | T-05, NFR-7 | Must | 60m | 4.2 |
| 4.4 | Item matching | FR-S25, S30 | Should | 90m | D6 |
| 4.5 | Fixed sector list | D7 | Could | 20m | D5 |

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
- If D1 is "port": add a PIN hash with scrypt, `POST /auth/login`, `POST /auth/change-pin`, and a lockout after 5 wrong PINs. Reference: `git show 1a81088:server/app/shared/auth.py` and `…/onboarding/index.py`.

**Acceptance:** an expired or logged-out token returns 401, and the app returns to onboarding (FR-C5).

### 3.6 Real-time updates (per D2)

**Scope:** if WebSocket, add `/ws?token=` that publishes `entry_saved`, `stock_changed` and `access_requested` events after commit. Reference: `git show 1a81088:server/app/shared/realtime.py`. If polling, there is no server work beyond 2.7 and 3.3.
**Acceptance:** Home and the dashboard update within 3 seconds of a saved entry.

### 3.7 Structured log per message (NFR-10)

**Scope:** one JSON log line per message with the trader ID, client message ID, input, interpretation, status, confidence, latency and LLM call count. Never log tokens.
**Acceptance:** a failed extraction can be explained from the logs alone.

### 3.8 Voice path finalised (per D3)

**Scope:** if the client transcribes on the device, document text-only use and keep server STT as optional. If the server transcribes, document `--convert` for whisper.cpp (it needs ffmpeg), or have the app record 16 kHz WAV. Test 5 Pidgin clips (PRD T-22).
**Acceptance:** an M4A or WAV recorded on the demo phone is saved with its transcript in `raw_text`.

## Phase 4: Quality and delivery

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

### 4.4 Item matching (per D6, `server/TODO.txt` item 1)

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
