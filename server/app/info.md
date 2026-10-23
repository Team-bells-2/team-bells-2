# `server/app`: vertical slice scaffold

Written for the two backend developers. Source of truth is [final-prd.md](../../final-prd.md); FR/NFR IDs below point to it.

## 1. Why vertical slices

Each folder under `app/` owns one feature end to end: its routes, request and response schemas, business logic and database models. We do not split by technical layer (`routers/`, `models/`, `services/`). Two people can then work in different folders without merge conflicts, and a ticket maps to one folder.

Every slice currently holds an empty `index.py`. That is its entry point. Add more files next to it (for example `schemas.py`, `models.py`, `service.py`) as the slice grows. Inside a slice, keep the layout consistent with the other slices once the first one is built.

```
app/
├── ledger/        ai/          customers/    ask/
├── consent/       onboarding/  profile/      inventory/
├── home/          suggestions/ demo/
└── shared/
    ├── env.py                    settings read from the root .env
    └── Infrastructure/
        ├── db/   (base.py, session.py)   SQLAlchemy Base, engine, get_db(), session_scope()
        ├── llm/                          LLM wrapper
        └── SST/                          speech-to-text wrapper
```

## 2. Rules that apply to every slice

1. **The database is the source of truth.** Totals, debts, profit, stock and supplier rankings are computed in code from the database. Model output never changes them (NFR-1). A test must prove this.
2. **The AI only interprets and phrases.** It never writes SQL, ranks suppliers, or supplies numbers shown to the user.
3. **Derived values are never hand-edited.** Debt balances come from entries. Quantity on hand comes from stock movements.
4. **Writes are atomic** (NFR-3). Use `session_scope()` so a failure leaves nothing half-saved.
5. **Trader endpoints require the session token** and return only that trader's data. Every query is filtered by `trader_id`.
6. **Errors share one shape:** `{ "error": { "code": "...", "message": "..." } }`.
7. **Settings come from `shared/env.py`.** No hardcoded config values.
8. **One wrapper for all LLM and speech calls** (caching, timeouts, `max_tokens`, call counter, `DEMO_MODE`). No slice calls a provider directly.

## 3. The slices

### `ledger`: capture and the entry history

- **Covers:** `POST /messages`, `GET /entries`; FR-S1 to S8, S28; NFR-5, NFR-10.
- **Responsibilities:**
  - Accept text (and voice, after transcription) from the app and return either `saved` or `clarify` with a one-line confirmation.
  - Run the pipeline: normalise shorthand in code (FR-S4: "ten k" = 10,000, "2.5k" = 2,500), call `ai` for extraction, validate with pydantic, save.
  - Hold a pending entry when fields are missing or confidence is low, ask exactly one short question, and complete the entry on the next message (FR-S5).
  - Apply corrections to the last entry in place and record the change in the audit trail (FR-S6).
  - Build the confirmation line from saved database fields, not from model text (FR-S7).
  - Return a polite fallback and write nothing for gibberish (FR-S8).
  - Dedupe on the client-generated message ID (NFR-5).
  - List entries newest first with filters by period and type, and paging.
- **Tables:** `entries`, `entry_edits`, `pending_clarifications`, `processed_messages`.
- **Key rule:** invalid or malformed model output never reaches the database. One retry, then a clarifying question (FR-S3).
- **Depends on:** `ai`, `customers` (resolve the customer), `inventory` (stock effect).

### `ai`: interpretation only

- **Covers:** extraction, name and item matching, intent routing, suggestion wording, and the LLM/speech wrapper (NFR-8). Related tickets: T-08, T-09, T-17, T-22.
- **Responsibilities:**
  - Extract a ledger entry (type, item, quantity, unit, amount_ngn, customer, due_date, confidence, raw_text) as schema-validated JSON.
  - Match customer names and inventory items against the trader's existing lists when the alias or name lookup fails.
  - Pick an `/ask` intent and its parameters from the whitelist.
  - Phrase the one-line reason for a restock suggestion from factors it is given.
  - Provide cached fixtures and `DEMO_MODE` so tests and the demo work offline.
- **Tables:** none.
- **Key rule:** `ai` returns data to other slices. It does not read or write the database, and it never decides a number. The provider clients themselves live in `shared/Infrastructure/llm` and `SST`.

### `customers`: memory and debts

- **Covers:** `GET /customers`; FR-S9, S10, S12.
- **Responsibilities:**
  - Store customers with aliases. Resolve "Ngozi" or "the rice woman" to Mama Ngozi using the alias table first, then `ai` against the existing customer list. If unsure, return a question such as "Do you mean Mama Ngozi?".
  - Compute balances from entries: credit sales add, payments received subtract. Example: a ₦60,000 credit sale and a ₦30,000 payment give a ₦30,000 balance.
  - Flag overdue entries past `due_date`. Resolve relative dates like "Friday" against the trader's current date (could-have).
- **Tables:** `customers`, `customer_aliases`.
- **Key rule:** balances are derived on read, never stored or edited.

### `ask`: questions about the business

- **Covers:** `POST /ask`; FR-S11.
- **Responsibilities:**
  - Turn a plain-language question into one whitelisted intent with parameters: `who_owes`, `customer_balance`, `today_total`, `stock_level`, `restock_suggestion`.
  - Run a fixed, parameterised query through the owning slice (`customers`, `ledger`, `inventory`, `suggestions`) and return the answer.
  - Return a fallback for an unknown intent.
- **Tables:** none.
- **Key rule:** the model picks the intent and parameters and never writes SQL. "Where I fit buy rice?" must return the same suppliers in the same order as `GET /suggestions`.

### `consent`: lender access with the trader's permission

- **Covers:** `POST /access-requests`, `GET /access-requests`, `POST /access-requests/{id}/approve`, `DELETE /access/{id}`, `GET /agent/summary`; FR-S13 to S17; NFR-6.
- **Responsibilities:**
  - Create pending requests (agent name, purpose, scopes). A request without purpose or scopes returns 422.
  - Let the trader approve or reject. Approval issues a scoped token with expiry (30 days, shorter for the demo). Rejection issues none.
  - Store tokens hashed. Revoke immediately on `DELETE`.
  - Serve `/agent/summary` with totals only: sales total, active days, total owed.
  - Log every agent call (agent, time, scope, result) for the dashboard, including expired, revoked and missing tokens.
- **Tables:** `access_requests`, `access_tokens`, `access_log`.
- **Key rule:** the summary response is an allow-list schema. No customer names, raw text, entry IDs, phone or location. A test asserts no customer name from the database appears in it. `POST /access-requests` is open (no auth) but returns no data.
- **Depends on:** `ledger` and `customers` for the totals only.

### `onboarding`: sign-up

- **Covers:** `POST /onboarding`; FR-S21; decision D7.
- **Responsibilities:**
  - Create a trader from name, phone, business name, sector, location (chosen from a seeded list of markets or areas) and main items sold, each with a unit and an optional opening quantity.
  - Create an inventory item per main item, and an opening stock movement when a quantity is given.
  - Issue a random session token, stored hashed. No OTP or password.
  - Reject a request missing name, phone, sector or location with 422.
- **Tables:** `traders`, `sessions`.
- **Depends on:** `inventory` (to create the items and opening stock).

### `profile`: the signed-in trader

- **Covers:** `GET /profile`, `PATCH /profile`; FR-S22.
- **Responsibilities:** return and update name, business name, sector and location. A missing or invalid token returns 401. One trader's token never returns another trader's data.
- **Tables:** reads and updates `traders` (created by `onboarding`).

### `inventory`: stock

- **Covers:** `GET /inventory`, `POST /inventory`, `PATCH /inventory/{id}`, `POST /inventory/{id}/stock`; FR-S23 to S26.
- **Responsibilities:**
  - List items with name, unit, quantity on hand, unit cost, reorder level and reorder quantity.
  - Add items and edit details. Editing details never changes quantity on hand.
  - Record stock movements (opening, restock, sale, adjustment). Quantity on hand is the sum of movements: 10 opening + 5 restock − 2 adjustment = 13.
  - On a saved sale or credit sale whose item matches inventory, create a sale movement. An unmatched item is saved with no stock change and flagged "not in inventory". A sale larger than stock is still saved and flagged "check stock".
  - On a saved expense that matches an item (for example 5 bags of rice), create a restock movement. An expense such as transport changes no stock.
  - When a correction changes an entry, update the same movement.
- **Tables:** `inventory_items`, `stock_movements`.
- **Key rule:** quantity on hand is derived, never hand-edited.

### `home`: profit and loss

- **Covers:** `GET /home?period=today|7d|30d`; FR-S27.
- **Responsibilities:** return revenue, expenses, profit, total owed, the number of items logged and the items at or below their reorder level, all computed in code.
- **Tables:** none; reads from `ledger`, `customers` and `inventory`.
- **Key rule:** revenue is sale and credit_sale amounts. Payments received are not revenue, because the credit sale already counted. Profit is revenue minus expenses and may be negative. Example: ₦50,000 sale + ₦60,000 credit sale − ₦40,000 expense gives revenue ₦110,000 and profit ₦70,000, with ₦30,000 owed after a ₦30,000 payment.

### `suggestions`: where to restock

- **Covers:** `GET /suggestions?item=&quantity=`; FR-S29 to S32.
- **Responsibilities:**
  - Hold synthetic supplier data: suppliers with area and coordinates, offers per item (unit, price, quantity available, quality grade A/B/C) and reviews (rating 1 to 5, comment). At least 4 suppliers per demo item (rice, beans, garri, oil) and at least 3 reviews each. Label it as demo data in the API.
  - Rank suppliers with a deterministic score from five factors: distance (computed in code from the trader's location), average rating, quality grade, unit cost, and quantity available against quantity needed. Weights live in one config file. Quantity defaults to the item's reorder quantity.
  - Return up to 3 suppliers with distance, price, rating, review count, grade, quantity and a one-line reason. The reason comes from `ai` with a template fallback if the model call fails.
- **Tables:** `suppliers`, `supplier_offers`, `supplier_reviews`.
- **Key rule:** the same data and request always return the same order. Improving one factor never lowers a supplier's rank, and a supplier that cannot fill the quantity ranks below those who can. The model never ranks.

### `demo`: seed and reset

- **Covers:** FR-C10; ticket T-16.
- **Responsibilities:** "Reset" returns the database to a clean state (no trader accounts, with supplier and review data loaded). "Seed" adds the demo trader, 4 to 5 customers (Mama Ngozi plus nicknames) and starting stock. Each finishes in under 10 seconds.
- **Tables:** writes across all slices; owns none.

### `shared`

- `env.py`: `Settings` (pydantic) reading the root `.env`. Required: `DATABASE_URL`, `DB_ECHO`, `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`.
- `Infrastructure/db`: `Base` (with a naming convention for Alembic), the engine, `SessionLocal`, `get_db()` for FastAPI dependencies and `session_scope()` for atomic units of work.
- `Infrastructure/llm` and `Infrastructure/SST`: provider wrappers (empty for now).

## 4. How a request flows between slices

Example: "I sell two bags rice to Mama Ngozi, sixty k, on credit".

1. `ledger` receives `POST /messages` and normalises "sixty k" to 60,000.
2. `ai` extracts the entry; `ledger` validates it with pydantic.
3. `customers` resolves "Mama Ngozi" (alias first, then `ai`).
4. `ledger` saves the entry. `inventory` adds a sale movement for the matched rice item.
5. `ledger` builds the confirmation line from the saved fields.
6. `home` and `customers` reflect the change on their next read, because both are derived from entries.

## 5. Dependencies between slices

Keep calls one-directional so the slices do not import each other in a loop.

```
ledger      -> ai, customers, inventory
ask         -> ai, customers, ledger, inventory, suggestions
home        -> ledger, customers, inventory
consent     -> ledger, customers          (totals only)
onboarding  -> inventory
suggestions -> ai (wording only)
customers   -> ai (matching only)
demo        -> every slice
```

`ai` and `shared` import nothing from the other slices.

## 6. Data model ownership

| Slice | Tables |
| --- | --- |
| onboarding | traders, sessions |
| ledger | entries, entry_edits, pending_clarifications, processed_messages |
| customers | customers, customer_aliases |
| inventory | inventory_items, stock_movements |
| consent | access_requests, access_tokens, access_log |
| suggestions | suppliers, supplier_offers, supplier_reviews |

A slice reads another slice's tables only through that slice's functions, not by importing its models.

## 7. Open points to agree between us

- Where the shared "current trader" dependency (session-token check) lives. Every trader endpoint needs it. Proposal: expose it from `onboarding` or put it in `shared`.
- The PRD's data model says SQLite (decision D2) and still needs updating for PostgreSQL.
- The dependency directions in section 5 and the "read through functions, not models" rule in section 6 are our proposal. The PRD does not state them.
- Dashboard endpoints (`/entries`, `/customers` with no token) need a decision on how the demo dashboard is allowed through.
- The PRD lists `backend/app/...` as the folder owners; our path is `server/app/...`.
- Alembic is not initialised yet.
