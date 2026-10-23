# OJA: Frontend Handoff

This contract follows [final-prd.md](final-prd.md), especially Sections 4, 7, and 8. **Status: planned.** The OJA backend in `server/` is still a scaffold; API field-level request/response shapes remain provisional until Sprint 0 freezes them.

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
