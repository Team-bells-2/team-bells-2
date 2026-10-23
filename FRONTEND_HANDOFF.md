# OJA: Frontend Handoff

This contract follows [final-prd.md](final-prd.md), especially Sections 4, 7, and 8. **Status: implemented in `server/`.** The live schema is at `/docs` (OpenAPI) when the server runs.

## Implementation notes the PRD does not spell out

- **Voice:** `POST /messages` takes JSON, not multipart: `{"audio_base64": "...", "audio_filename": "voice.m4a", "client_message_id": "..."}`. The response carries `transcript`. A failed transcription returns `status: "fallback"` and writes nothing, so resend with the same `client_message_id`.
- **Message statuses:** `saved` (with `confirmation` and `entry`; `updated: true` for a correction), `clarify` (show `question`, send the trader's reply as the next message), `fallback`.
- **Questions** ("who owes me?") go to `POST /ask`, not `/messages`. Response: `{intent, answer, ...}`.
- **Consent for agents:** `POST /access-requests` takes `trader_phone`, `agent_name`, `purpose`, `data_scopes` (any of `sales_total`, `active_days`, `total_owed`) and returns `request_id` and a one-time `claim_secret`. The agent polls `GET /access-requests/{id}/status` with header `X-Claim-Secret`; after approval the response carries `access_token` exactly once.
- **Approve or reject** from the app: `POST /access-requests/{id}/approve` with `{"approve": true|false}`. `GET /access-requests` items include a ready-made `prompt` string and the access `log`.
- **Home** includes `recent_entries` and, for each low-stock item, `top_suggestion`.

## Accounts: sign-up and login

Phone number plus a 4 to 6 digit PIN. Every auth call returns `{trader_id, session_token, token_type, expires_at}`; send the token as `Authorization: Bearer <token>`.

| Endpoint | Body | Notes |
| --- | --- | --- |
| `POST /auth/signup` (same as `POST /onboarding`) | onboarding fields + `pin` | 409 if the phone already exists |
| `POST /auth/login` | `{phone, pin}` | 401 `invalid_credentials`; after 5 wrong PINs, 429 `account_locked` for 5 minutes |
| `POST /auth/logout` | none | Ends this device's session only. Returns 204 |
| `POST /auth/change-pin` | `{current_pin, new_pin}` | Returns 204 |

App flow: no stored token → Login screen with a "Create account" link to onboarding. Any 401 → back to Login. The demo trader is phone `08030000001`, PIN `1234`.

## Real-time updates (WebSocket)

Connect to `ws://<server>/ws?token=<session_token>` after login (use `wss://` behind HTTPS). Actions still use the REST endpoints; the socket only pushes what changed, so screens update without polling. Send the text `ping` every 25 seconds to keep a phone connection alive; the server answers `pong`. A close with code 4401 means the token is invalid: go back to Login. On any other close, reconnect after a few seconds and refetch the screen.

Every message is `{"type": ..., "data": ..., "at": ISO time}`:

| type | data | Refresh |
| --- | --- | --- |
| `connected` | `{trader_id}` | |
| `entry_saved`, `entry_updated` | the entry, as in `GET /entries` | Home, Items logged, Inventory |
| `inventory_changed` | the item, as in `GET /inventory` | Inventory, Home |
| `access_requested` | `{id, agent_name, purpose, scopes, prompt}` | Show the Approve / Reject prompt at once (FR-C3) |
| `access_decided`, `access_revoked` | `{id, status?, expires_at?}` | Profile, connected agents |
| `access_log` | `{request_id, result}` | Dashboard access log |
| `profile_updated` | the profile | Profile |

The server runs one process, so start uvicorn with a single worker.

## Client Rules

- The database is the source of truth. Never compute totals, debts, profit, stock, or supplier rankings in the UI.
- Keep network calls behind one API client. The base URL is configuration so a phone can reach a laptop on the local network.
- JSON uses `snake_case`; amounts are NGN numbers formatted in the UI; timestamps are ISO 8601.
- Errors use `{ "error": { "code": "...", "message": "..." } }`. Show failures as retryable, never as success.
- Trader endpoints use the onboarding session token in `Authorization: Bearer <token>`. Store it on-device; a 401 returns the user to onboarding.
- Send a client-generated `client_message_id` with each message to prevent duplicate entries on retry.

## Planned Endpoints

| Endpoint | Used by | Auth |
| --- | --- | --- |
| `POST /onboarding` | App | None; returns session token |
| `GET /profile`, `PATCH /profile` | App | Session token |
| `POST /messages` (text or voice file) | App | Session token |
| `GET /entries` (period/type filters, paging) | App, dashboard | Session token (app) |
| `GET /customers` | App, dashboard | Session token (app) |
| `POST /ask` | App | Session token |
| `GET /home?period=today\|7d\|30d` | App | Session token |
| `GET /inventory`, `POST /inventory` | App | Session token |
| `PATCH /inventory/{id}`, `POST /inventory/{id}/stock` | App | Session token |
| `GET /suggestions?item=&quantity=` | App | Session token |
| `GET /access-requests?status=pending` | App | Session token |
| `POST /access-requests/{id}/approve` | App | Session token |
| `DELETE /access/{id}` | App | Session token |
| `POST /access-requests` | Lender agent | None |
| `GET /agent/summary` | Lender agent | Scoped bearer token |
| `GET /health` | CI | None |

The contract will be frozen at the end of Sprint 0. Until then, names and response shapes are provisional; coordinate changes with backend and QA before wiring screens.

## Screens

Bottom navigation: Home, Assistant, Inventory, Profile.

- **Onboarding:** name, phone, business name, sector, market/area, and main items with optional opening stock. One short step at a time; validate before submit.
- **Home:** profit/loss (revenue, expenses, profit) with today/7 days/30 days selector, total owed, newest logged items, and low-stock restock suggestions. Update within 3 seconds of a new entry. Item details show `raw_text`.
- **Assistant:** type or record a voice note, send it to `/messages`, and show confirmation or a clarifying question. Show voice processing and clear backend/transcription failure states.
- **Inventory:** items, quantity, unit, unit cost and low-stock highlight. Add/edit items, opening stock, restock or adjustment. “Where to restock” opens suggestions.
- **Profile:** edit merchant details. Show connected agents with scope, expiry and Revoke. Poll pending access requests and show Approve/Reject.
- **Restock suggestions:** up to 3 seeded suppliers with distance, unit price, rating, quality, quantity available and reason. Label all seeded supplier data “Demo data”.

## Judges' Dashboard

Show entries newest first with `raw_text`, customer balances and overdue flags, agent requests/scopes/revocation status/access log. Updates should appear within 3 seconds without manual refresh. Provide Reset and Seed controls.

## Legacy Prototype Note

The old `backend.py/` prototype has ArketData price comparisons, user-submitted market reviews and Open-Meteo weather routes. These are **not part of the current OJA client contract**. OJA uses the seeded synthetic supplier/offer/review dataset in `final-prd.md` Sections 4.6 and 6. Do not call prototype `/markets` routes from the Flutter client unless the PM updates and freezes the OJA PRD/API contract.

## Agent Action Log

- 2026-10-23: Handoff aligned to OJA and `final-prd.md`; old MerchantPal API is identified as a separate legacy prototype.
- 2026-10-23: First OJA slices implemented in `server/app/` (SQLAlchemy ORM, Postgres): `onboarding` (traders, sessions, new `locations` table), `profile`, `customers`.
  - Live for the client: `POST /onboarding` (201, returns `token` + `trader`; 409 `phone_taken`; 422 `unknown_location`), `GET`/`PATCH /profile`, `GET /customers` (names only, balances come with the ledger), `GET /health`.
  - Auth: `Authorization: Bearer <token>`; missing/invalid token returns 401 (`missing_token` / `invalid_token`).
  - Errors use `{ "error": { "code", "message" } }`, including 422 validation errors.
  - Not yet: main items/opening stock at onboarding, location list endpoint, customer balances, Alembic migrations, login.
- 2026-10-23: `customers` slice moved to clean-architecture wiring (no API change): router -> `CustomerOrchestrator` -> `CustomerRepository` -> Session, injected with FastAPI `Depends`.
- 2026-10-23: `onboarding` and `profile` moved to the same clean-architecture wiring as `customers` (no API change). Added `onboarding/repositories/` (location, trader, session) and `shared/Infrastructure/db/base_repository.py` (commit/rollback/refresh).
- 2026-10-23: Ledger, inventory (read-only) and home slices added; customers gains aliases and balances. Resolves review reds 4-7 (PRD accounting model, alias-first customer matching, per-trader pending clarification, single-transaction writes).
  - New for the client: `GET /entries?period=today|7d|30d&type=&limit=&offset=`, `GET /inventory` (derived `quantity_on_hand`, `low_stock`), `GET /home?period=today|7d|30d` (revenue, expenses, profit = revenue - expenses, total owed, items logged, low-stock items).
  - `GET /customers` now includes `balance_ngn` (derived; negative = overpaid).
  - Money and quantities are JSON numbers. Periods start at Lagos midnight.
  - `POST /messages` is not exposed yet; it needs the AI slice. The ledger workflow behind it (save / clarify / complete / correct) is built and tested.
- 2026-10-23: Reds 8-15 resolved. `POST /messages` is live; `GET /suggestions` added.
  - `POST /messages` text: JSON `{ "text", "client_message_id" }`. Voice: multipart fields `audio` (file) + `client_message_id`. Generate a new `client_message_id` per message and reuse it on retry: a retry returns the original reply unchanged.
  - Response: `{ status: saved|corrected|clarify|fallback, message, entry?, flags[], transcript? }`. Show `message` in the chat; `transcript` is set for voice notes.
  - Audio types: WAV, MP3, M4A, AAC, OGG, WebM, FLAC (max 15 MB). `application/octet-stream` is rejected with 415, so send the real content type.
  - Errors: 503 `ai_unavailable` (retry later), 502 `transcription_failed` (resend or type), 415 `unsupported_audio`, 413 `audio_too_large`.
  - `GET /suggestions?item=&quantity=`: up to 3 suppliers (distance_km, unit_price_ngn, average_rating, review_count, quality_grade, quantity_available, can_fill, reason) and `data_label: "Demo data"`. Quantity defaults to the item's reorder quantity; 422 `quantity_required` if there is none.
  - Old `/markets`, `/markets/reviews` and `/transcribe` routes were not ported.
- 2026-10-23: Alembic initialised (`alembic.ini` at repo root, scripts in `server/app/shared/Infrastructure/db/alembic`). Initial migration applied to the local Postgres; reference data seeded (8 locations, 6 demo suppliers). Run `alembic upgrade head` from the repo root, then `cd server && python -m app.demo.index`. Item-name matching is an open team question (`server/TODO.txt`).
- 2026-10-23: Post-merge validation on `wade-latest-23-44` (rebase in progress). Fixed missing `Field` import in `server/app/shared/env.py` (app could not start). Our slices pass all checks on Postgres; the teammate's server code in the slices' `index.py` files, `shared/auth.py`, `shared/realtime.py` and `consent/` is present but not mounted. PRD gap review follows.
