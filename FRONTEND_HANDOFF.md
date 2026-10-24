# OJA: Frontend Handoff

The API contract for the Flutter app, the judges' dashboard and the lender agent, as served by `server/` today. Requirements: [final-prd.md](final-prd.md) (sections 4, 7, 8). Live schema: `/docs` when the server runs. Planned work: [server/IMPLEMENTATION_PLAN.md](server/IMPLEMENTATION_PLAN.md).

The response examples below were captured from the running app.

## Rules for the client

- **Base URL:** keep it in config, so the phone can reach the laptop on the local network (e.g. `http://192.168.x.x:8000`).
- **Auth:** trader endpoints need `Authorization: Bearer <token>`, using the token from `POST /onboarding`. Store it on the device. A `401` means the token is missing or invalid: send the user back to onboarding (FR-C5). The lender agent uses its own access token (see Consent).
- **JSON:** fields are `snake_case`. Money (`*_ngn`) and quantities are JSON numbers, so format them in the UI. Timestamps are ISO 8601 (UTC). Home and entry periods start at Lagos midnight. Dates (`due_date`) are `YYYY-MM-DD`.
- **Figures come from the server.** Never compute totals, balances, profit, stock or rankings in the app.
- **Errors** always have one shape: `{ "error": { "code": "...", "message": "..." } }`. Show `message`, and branch on `code`.
- **Messages:** generate a new `client_message_id` for each message, and reuse it when you retry the same message. A retry returns the original reply and never creates a second entry (NFR-5).

## Endpoints

| Endpoint | Auth | Purpose |
| --- | --- | --- |
| `GET /health` | none | Liveness |
| `POST /onboarding` | none | Create a trader (and their main items), get a session token |
| `POST /auth/login` | none | Phone + PIN; returns a new session token |
| `POST /auth/logout`, `POST /auth/change-pin` | token | End this device's session; set or change the PIN |
| `GET /profile`, `PATCH /profile` | token | Read or edit the trader |
| `POST /messages` | token | Text or voice message: save, correct, clarify or fall back |
| `GET /messages/history` | token | The assistant chat (both sides of every turn), to restore it after a restart |
| `GET /entries` | token | Ledger entries, newest first |
| `GET /customers` | token | Customers with aliases, derived balances and overdue flags |
| `GET /inventory`, `POST /inventory` | token | List items, add an item |
| `PATCH /inventory/{id}`, `POST /inventory/{id}/stock` | token | Edit an item's details, record opening stock, restock or adjustment |
| `GET /home` | token | Profit and loss, total owed, low stock with a restock card, recent entries |
| `GET /suggestions` | token | Up to 3 restock suppliers for an item |
| `POST /ask` | token | Questions: who owes me, a customer's balance, today's sales, stock, where to restock |
| `GET /access-requests`, `POST /access-requests/{id}/approve`, `DELETE /access/{id}` | token | The trader's consent prompt, decision and revoke |
| `POST /access-requests`, `GET /access-requests/{id}/status` | none / claim secret | Lender agent asks for access and collects its token |
| `GET /agent/summary` | agent token | Totals-only summary for the lender agent |
| `WS /ws?token=<session token>` | Trader session token | Authenticated change notifications; reconnect and refresh through REST |
| `POST /demo/reset`, `POST /demo/seed` | none, only when `DEMO_CONTROLS_ENABLED=true` | Clear all traders; create the demo trader and get its token |

### `POST /onboarding`

`location_name` must be one of the seeded markets or areas: Mile 12, Oyingbo, Ketu, Agege, Mushin, Yaba, Oshodi, Ajah. Matching ignores case, and the trader's coordinates come from the chosen location.

`items` is optional (up to 40). Each item becomes an inventory item; `opening_quantity` adds its opening stock.

`pin` is optional: 4 to 6 digits. With a PIN, the trader can log in again later with phone + PIN; it can also be set later with `/auth/change-pin`.

```json
{ "name": "Ada Obi", "phone": "08031234567", "business_name": "Ada Foods",
  "sector": "foodstuff", "location_name": "Mile 12",
  "items": [ { "name": "rice", "unit": "bag", "unit_cost_ngn": 58000, "opening_quantity": 10,
               "reorder_level": 3, "reorder_quantity": 10 } ] }
```

`201`:

```json
{ "token": "L4SaLAHKOgYx…",
  "trader": { "id": 1, "name": "Ada Obi", "phone": "08031234567", "business_name": "Ada Foods",
              "sector": "foodstuff", "location_name": "Mile 12", "latitude": 6.605, "longitude": 3.398,
              "created_at": "2026-10-24T00:00:51Z" } }
```

| Case | Status | `error.code` |
| --- | --- | --- |
| Phone already registered | 409 | `phone_taken` |
| Unknown location | 422 | `unknown_location` |
| Missing field, or the same item name twice | 422 | `validation_error` |

### Accounts: login, logout, PIN

- **Session tokens** expire after `SESSION_TOKEN_TTL_DAYS` (30 by default). An expired, logged-out or unknown token gives `401`: send the trader to login (or onboarding when they have no PIN).
- **`POST /auth/login`** `{ "phone": "08031234567", "pin": "1234" }` → `200`, same shape as onboarding (`token`, `trader`). A wrong phone, a trader without a PIN and a wrong PIN all give `401 invalid_credentials`. After 5 wrong PINs in a row, login is locked for 5 minutes: `429 account_locked` (both limits are server settings).
- **`POST /auth/logout`** → `204`. Ends this device's session only, and closes its WebSocket.
- **`POST /auth/change-pin`** `{ "current_pin": "1234", "new_pin": "4321" }` → `204`. `current_pin` is required once a PIN exists (wrong → `401`); a trader without a PIN sends only `new_pin`.

### `GET /profile` and `PATCH /profile`

GET returns the trader object above. PATCH accepts any of `name`, `business_name`, `sector` and `location_name`, and returns the updated trader. A new location also updates `latitude` and `longitude`. Any other field, such as `phone`, returns `422`.

### `POST /messages`

**Text:** JSON `{ "text": "...", "client_message_id": "a1b2c3" }`.

**Voice:** `multipart/form-data` with the fields `audio` (the file, with its real content type) and `client_message_id`. Accepted types: WAV, MP3, M4A, AAC, OGG, WebM, FLAC. Maximum size: `STT_MAX_UPLOAD_MB` (15 MB by default).

**Response** (`200`):

```json
{ "status": "saved",
  "message": "Saved: credit sale to Mama Ngozi for ₦60,000 due Fri 30 Oct.",
  "entry": { "id": 2, "type": "credit_sale", "item": null, "quantity": null, "unit": null,
             "amount_ngn": 60000.0, "customer": "Mama Ngozi", "due_date": "2026-10-30", "confidence": 0.95,
             "status": "saved", "stock_warning": null,
             "raw_text": "Mama Ngozi carry rice sixty k, she go pay Friday",
             "created_at": "…", "updated_at": "…" },
  "flags": [],
  "transcript": null }
```

| `status` | Meaning | What the app shows |
| --- | --- | --- |
| `saved` | A new entry was saved | `message`; refresh Home and the entries |
| `corrected` | The last entry was changed in place (same `entry.id`) | `message` |
| `clarify` | One question; nothing is saved yet | `message` as the assistant's question. Send the trader's reply as the next message |
| `fallback` | Off-topic message, or the trader said "no" to a confirmation; nothing is saved | `message` |

- **Questions the assistant asks** (all built by the server):
  - "How much did you collect for the 2.5 bags?" or "How much did you pay for the 5 bags?" (amount missing)
  - "How much was it?", "Which customer is this for?"
  - "Do you mean oil?" (goods named differently from the trader's inventory, e.g. "palm oil"). Reply "yes" to count it against that item's stock; "no" saves it as not in inventory.
  - "Do you mean Mama Ngozi?" (a new name that may be an existing customer). Reply "yes" to link it and remember the name; "no" to create a new customer.
  - "Do you mean Mama Bisi or Mama Ngozi?" (a name shared by two customers). Reply with the full name.
  - "Just to confirm: sale of rice, ₦10,000?" (the reading was unsure). Reply "yes" to save, "no" to discard.
- **Yes and no** are understood in English and Pidgin ("yes", "ok", "na she", "e be so", "no", "no be she").
- **Starting over:** while a question is waiting, a different, complete entry (for example "I pay transport 2k") replaces the waiting one.
- **`raw_text`** joins the trader's messages for one entry with ` | ` (e.g. `"I sell two bags and half | 25k"`). For voice it is the transcript, also returned as `transcript`.
- **`due_date`:** for credit sales, phrases like "Friday", "tomorrow" or "next week" become a date.
- **`flags` and `entry.stock_warning`:** `not_in_inventory` means a sale of an item the trader doesn't stock. `check_stock` means the sale was larger than the stock on hand: the entry is saved but stock is not moved.

| Error | Status | `error.code` | App action |
| --- | --- | --- | --- |
| Assistant unavailable | 503 | `ai_unavailable` | Say so, and retry later with the same `client_message_id` |
| Voice not understood | 502 | `transcription_failed` | Ask the trader to resend or type |
| Unsupported or generic audio type | 415 | `unsupported_audio` | Send the real content type |
| Voice note too large | 413 | `audio_too_large` | Record a shorter note |
| Correction with nothing to correct | 409 | `no_entry_to_correct` | Show `message` |
| Missing field | 422 | `validation_error` | Fix the request |

### `GET /messages/history`

The trader's assistant chat, one per trader (the same on every device). Query parameters: `limit` (1 to 500, default 100) and `before_id` (for older pages). Returns the newest `limit` messages, **oldest first**:

```json
{ "messages": [
    { "id": 7, "role": "trader", "text": "I sell two bags and half", "entry_id": null, "created_at": "…" },
    { "id": 8, "role": "assistant", "text": "How much did you collect for the 2.5 bags?", "entry_id": null, "created_at": "…" },
    { "id": 9, "role": "trader", "text": "145k", "entry_id": null, "created_at": "…" },
    { "id": 10, "role": "assistant", "text": "Saved: sale for ₦145,000.", "entry_id": 8, "created_at": "…" } ],
  "has_more": true }
```

- Every `POST /messages` reply (saved, corrected, clarify, fallback) and every `POST /ask` answer adds two messages: the trader's text and the assistant's reply. For voice, the trader's text is the transcript.
- `entry_id` is set on the assistant reply that saved or corrected an entry; open it from `GET /entries`.
- Failed requests (503, 502, network errors) are not stored. A retry with the same `client_message_id` is stored once.
- When `has_more` is true, load older messages with `before_id=<id of the first message you have>`.
- The opening greeting is the app's own text and is not stored.

### `GET /entries`

Query parameters: `period` (`today`, `7d` or `30d`), `type` (`sale`, `credit_sale`, `payment_received` or `expense`), `limit` (1 to 200, default 50) and `offset`. Returns a JSON array of entry objects (same shape as `entry` above), newest first.

### `GET /customers`

```json
[ { "id": 1, "canonical_name": "Mama Ngozi", "aliases": ["the rice woman"], "created_at": "…",
    "balance_ngn": 30000.0, "overdue": false } ]
```

- `balance_ngn` is computed from entries: credit sales add and payments subtract. A negative value means the customer overpaid.
- `overdue` is true while the customer still owes and a credit sale is past its due date.

### Inventory

`GET /inventory` returns the items:

```json
[ { "id": 2, "name": "garri", "unit": "bag", "quantity_on_hand": 2.0, "unit_cost_ngn": 25000.0,
    "reorder_level": 3.0, "reorder_quantity": 8.0, "low_stock": true } ]
```

| Request | Body | Notes |
| --- | --- | --- |
| `POST /inventory` → `201` | `{ "name", "unit", "unit_cost_ngn"?, "reorder_level"?, "reorder_quantity"? }` | Same name (ignoring case) → `409 item_exists` |
| `PATCH /inventory/{id}` | any of the fields above | Never changes quantity; `quantity_on_hand` in the body → `422` |
| `POST /inventory/{id}/stock` → `201` | `{ "quantity_change": 5, "reason": "opening" \| "restock" \| "adjustment" }` | Opening and restock must be positive; an adjustment may be negative; stock can't go below 0 → `409 negative_stock` |

All three return the item. Another trader's item → `404 item_not_found`. Sales reduce stock through `POST /messages`, never here.

### `GET /home?period=today|7d|30d`

```json
{ "period": "7d", "period_start": "2026-10-18T00:00:00+01:00",
  "revenue_ngn": 85000.0, "expenses_ngn": 0.0, "profit_ngn": 85000.0, "total_owed_ngn": 30000.0,
  "items_logged": 3,
  "low_stock_items": [
    { "id": 2, "name": "garri", "unit": "bag", "quantity_on_hand": 2.0, "unit_cost_ngn": 25000.0,
      "reorder_level": 3.0, "reorder_quantity": 8.0, "low_stock": true,
      "top_suggestion": { "supplier_id": 3, "supplier_name": "Mama Chioma Stores", "area": "Ketu",
                          "distance_km": 1.3, "unit": "bag", "unit_price_ngn": 40000.0,
                          "average_rating": 4.67, "review_count": 3, "quality_grade": "A",
                          "quantity_available": 40.0, "can_fill": true,
                          "reason": "Recommended: 1.3 km away, ₦40,000 per bag." } } ],
  "recent_entries": [ "…the 10 newest entries, same shape as GET /entries…" ] }
```

- Revenue is sales plus credit sales. Payments received are not revenue. Profit is revenue minus expenses, and can be negative.
- `total_owed_ngn` adds up only what customers owe; overpayments don't reduce it.
- `top_suggestion` is the same first supplier as `GET /suggestions` for the item's reorder quantity. It is `null` when the item has no reorder quantity. Show it with the "Demo data" label (FR-C17).

### `GET /suggestions?item=rice&quantity=10`

```json
{ "item": "rice", "quantity_needed": 10.0, "data_label": "Demo data",
  "suggestions": [ { "supplier_id": 3, "supplier_name": "…", "area": "…", "distance_km": 1.3, "unit": "bag",
                     "unit_price_ngn": 80000.0, "average_rating": 4.67, "review_count": 3,
                     "quality_grade": "A", "quantity_available": 12.0, "can_fill": true,
                     "reason": "…" } ] }
```

- Up to 3 suppliers, ranked in code. Show the "Demo data" label.
- `quantity` defaults to the item's reorder quantity. If there is none, the response is `422 quantity_required`.
- `reason` is wording only (from the model, or "Recommended: …" quoting real figures when the model is unavailable). Every figure comes from the database.

### `POST /ask`

```json
{ "question": "Who owes me?" }
```

```json
{ "intent": "who_owes", "answer": "Mama Ngozi ₦30,000. Total ₦30,000.",
  "customers": [ { "name": "Mama Ngozi", "balance_ngn": 30000.0, "overdue": false } ],
  "sales_ngn": null, "stock": null, "suggestions": null }
```

| `intent` | Example questions | Filled field |
| --- | --- | --- |
| `who_owes` | "Who owes me?", "who dey owe me" | `customers` (largest debt first) |
| `customer_balance` | "How much Ngozi dey owe?" | `customers` (one) |
| `today_total` | "How much I sell today?" | `sales_ngn` |
| `stock_level` | "How many rice remain?" | `stock` (an inventory item) |
| `restock_suggestion` | "Where I fit buy rice?" | `suggestions` (same as `GET /suggestions`) |
| `unknown` | anything else | none; `answer` lists what can be asked |

Show `answer`. Every figure in it comes from the database. For a restock question about an item with no reorder quantity, `answer` asks how many are needed.

### Consent and the lender agent

**1. The agent asks for access** (no auth, no business data returned):

```json
POST /access-requests
{ "trader_phone": "08031234567", "agent_name": "QuickLoan agent", "purpose": "Check credit readiness",
  "data_scopes": ["sales_total", "total_owed"] }
```

`202`: `{ "request_id": 1, "status": "pending", "claim_secret": "L0g5Yt…" }`.

- `data_scopes` are any of `sales_total`, `active_days` and `total_owed`.
- Missing purpose or scopes → `422`. Unknown phone → `404 trader_not_found`.

**2. The app shows the prompt.** Poll `GET /access-requests?status=pending` (FR-C3: within 5 seconds):

```json
[ { "id": 1, "agent_name": "QuickLoan agent", "purpose": "Check credit readiness",
    "scopes": ["sales_total", "total_owed"], "status": "pending", "requested_at": "…",
    "decided_at": null, "expires_at": null,
    "prompt": "QuickLoan agent wants to see your sales total, total owed for 30 days. Approve?",
    "log": [ { "endpoint": "POST /access-requests", "result": "requested", "at": "…" } ] } ]
```

**3. The trader decides:** `POST /access-requests/{id}/approve` with `{ "approve": true }` or `{ "approve": false }`. It returns the request; deciding twice → `409 already_decided`.

**4. The agent collects its token** with `GET /access-requests/{id}/status` and the header `X-Claim-Secret: <claim_secret>`:

```json
{ "request_id": 1, "status": "approved", "scopes": ["sales_total", "total_owed"],
  "access_token": "BCgbZ0xg…", "token_type": "bearer", "expires_at": "2026-11-23T00:00:51Z" }
```

The token is returned exactly once. Later polls show `"token_already_collected": true`. A wrong secret → `404`.

**5. The agent reads the summary:** `GET /agent/summary` with `Authorization: Bearer <access_token>`:

```json
{ "period_days": 30, "generated_at": "…", "scopes": ["sales_total", "total_owed"],
  "sales_total_ngn": 85000.0, "total_owed_ngn": 30000.0 }
```

Only the approved scopes appear (`active_days` when granted). There are never customer names, raw text, entry IDs, phone or location.

| Agent token | Status | `error.code` |
| --- | --- | --- |
| Missing | 401 | `missing_token` |
| Unknown | 401 | `invalid_token` |
| Expired | 401 | `expired` |
| Revoked | 403 | `revoked` |

**6. Revoke:** `DELETE /access/{id}` from the app. It takes effect at once. Every agent call and decision appears in the request's `log`.

### Demo controls, offline mode, browsers

- **`POST /demo/seed`** (only when the server sets `DEMO_CONTROLS_ENABLED=true`, else `403 demo_controls_disabled`) creates the demo trader if needed and returns `{ "trader_id", "phone": "08030000001", "pin": "1234", "token", "token_type": "bearer" }`. The trader (Tolu Adeyemi, Mushin) has rice, beans, garri (below its reorder level) and oil in stock, and customers Mama Ngozi ("Ngozi", "the rice woman"), Mr Bayo ("Bayo", "Oga Bayo"), Aunty Funke ("Funke") and Iya Sade ("Sade", "the pepper seller"). Safe to call twice; each call returns a new token.
- **`POST /demo/reset`** deletes every trader and their data (locations and suppliers stay).
- **`DEMO_MODE=true`** on the server: no model calls; messages are read by rules. The API contract is the same.
- **Browsers** (a web dashboard) can call the API only from origins listed in the server's `CORS_ORIGINS`. The Flutter app is not affected.

## Planned (not served yet)

| Work | Task |
| --- | --- |
| Judges' dashboard page | Not in scope; demo controls remain API-only |
| Structured per-message logging | 3.7 |
| Final voice-path validation and five Pidgin clips | 3.8 |

## WebSocket notifications

Connect to `/ws?token=<session token>` using the trader session token. Missing, invalid,
expired or revoked tokens close with code `4401`. The server accepts the text message
`ping` and replies `pong`. Change notifications are JSON objects with `type`, `data` and
`at`; event types are `entry_saved`, `entry_updated`, `inventory_changed`,
`profile_updated`, `access_requested`, `access_decided`, `access_revoked` and `access_log`.
They are sent after the corresponding database commit and only to sockets for that trader.
An open socket is also closed with `4401` when its session logs out (`POST /auth/logout`) or
expires; reconnect with a fresh token. `inventory_changed` is sent for every item whose stock
moved, including the old item when a correction changes the item.
Treat an event as an invalidation signal and refetch authoritative data through the REST
endpoints above. The in-memory hub requires a single Uvicorn worker. This documents the
server contract only; the Flutter client is not changed in this task.

## Screens (from the PRD)

Bottom navigation: Home, Assistant, Inventory, Profile.

- **Onboarding:** name, phone, business name, sector, market or area, and main items with optional opening stock.
- **Home:** profit and loss card with a period selector, total owed, "Items logged" from `recent_entries`, low-stock items with their restock card.
- **Assistant:** type or record a voice note. Show `message` from `POST /messages`, and route questions to `POST /ask`. Show a processing state for voice and a clear message on 503 or 502.
- **Inventory:** the list from `GET /inventory` with the low-stock highlight; add items, edit details, add opening stock, restock or adjustment. "Where to restock" opens `GET /suggestions`.
- **Profile:** edit the trader's details; connected agents from `GET /access-requests` with scope, expiry and a Revoke button (`DELETE /access/{id}`). Show the consent prompt when a pending request appears.

## Agent Action Log

- 2026-10-24: Chat history. New `GET /messages/history` (one chat per trader, oldest first, `limit` and `before_id` paging); `POST /messages` and `POST /ask` store both sides of each turn, with `entry_id` on replies that saved or corrected an entry. Migration `9fd76fded38f` (chat_messages). The Flutter Assistant restores the chat from it on start.
- 2026-10-24: Flutter client moved to this API (`client/lib/core/api/`, `client/lib/core/ledger/ledger.dart`). It logs in with phone + PIN from `config.dart` (`--dart-define=OJA_TRADER_PHONE` / `OJA_TRADER_PIN`) and onboards that trader with rice, beans, garri and oil on first launch. Typed and spoken text (speech recognised on the phone) go to `POST /messages`; questions go to `POST /ask`; Home, Inventory and restock read `/home`, `/entries`, `/customers`, `/inventory` and `/suggestions`. Audio upload and the WebSocket are not used yet. `render.yaml` now deploys `server/` with PostgreSQL.
- 2026-10-24: Phase 3.5/3.6 decisions recorded. Optional PINs are supported at onboarding or later; legacy sessions without expiry are assigned `created_at + SESSION_TOKEN_TTL_DAYS` on first authentication. Added authenticated WebSocket notifications for ledger, inventory, profile and consent events; no Flutter or dashboard-page changes.

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
- 2026-10-24: Wrote `server/IMPLEMENTATION_PLAN.md`: 25 tasks in 4 phases (clean-up, golden path, demo safety, quality) plus 6 open decisions. Correction to the earlier review: the Flutter client makes no API calls yet, so it is not bound to the teammate's API contract.
- 2026-10-24: Phase 1 of `server/IMPLEMENTATION_PLAN.md` done. Removed the teammate's unmounted server code (business rules kept in `server/BUSINESS_REQUIREMENTS.txt`, source at `1a81088`). Restored `session.py` (no `create_all`). `env.py`: 30 required keys, no code defaults; `.env.example` regrouped. Rewrote this handoff and the README to the live contract. Added 52 repo tests (`server/tests/`, 58 in total, SQLite or `TEST_DATABASE_URL`). Fixed an unclosed multipart upload file in `POST /messages`. No API change.
- 2026-10-24: Phase 2 of `server/IMPLEMENTATION_PLAN.md` done (tasks 2.1 to 2.7). New: `POST /inventory`, `PATCH /inventory/{id}`, `POST /inventory/{id}/stock`; main items at onboarding; "Do you mean X?" with yes/no and alias saving; context-aware questions; a different complete entry replaces a pending one; due dates from phrases ("Friday") computed in code; `overdue` and `aliases` on `/customers`; `stock_warning` on entries (oversell saves with no stock movement); Home `top_suggestion` and `recent_entries`; `POST /ask`; consent (`/access-requests`, approve, revoke, `/agent/summary`). Migrations `c3819b46ad50` (entries.stock_warning) and `5b14d59c5953` (consent tables). Business rules validated and decided are recorded in `server/BUSINESS_REQUIREMENTS.txt`. 114 tests pass on SQLite and PostgreSQL.
- 2026-10-24: Phase 3 review fixes. The WebSocket authenticates with a short-lived database session (an open socket holds no connection); logout and session expiry close open sockets with 4401; the hub keeps references to its send tasks; the ledger's event publisher is injected like the other orchestrators; `inventory_changed` covers every item whose stock moved (including the old item on a correction); legacy sessions' expiry (created_at + TTL) is computed on read instead of written during auth. 12 WebSocket/event tests added; 155 tests pass.
- 2026-10-24: Phase 4 (demo scope). Eval harness in `server/eval/` (`make eval`: offline 37 of 40); Makefile at the repo root; GitHub Actions runs the backend tests on pushes to `oja`; item and unit names now match ignoring case, spaces and plural endings ("rices" = "rice", "bags" = "bag"), and a sale in a different unit is saved with `check_stock` and no stock movement. No API shape changed. 165 tests pass.
- 2026-10-24: Item names now follow FR-S25: name first (ignoring case, spaces and plurals), then the model against the trader's inventory; unsure matches ask "Do you mean oil?" (yes/no), otherwise the entry is saved as `not_in_inventory`. Documented the auth endpoints, the optional onboarding `pin`, demo controls, `DEMO_MODE` and CORS for the Flutter integration. No existing response shape changed.
- 2026-10-24: CI extended: a PostgreSQL 16 job (migrations, seed, tests, end-to-end smoke against a running server) and pull-request triggers. Added `server/e2e/smoke.py`. No API change.
