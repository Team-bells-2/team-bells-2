# OJA: Frontend Handoff

Contract for the Flutter app and the judges' dashboard. The source of truth is [final-prd.md](final-prd.md) (sections 4, 7 and 8). **Status: planned.** The OJA backend in `server/` has no endpoints yet. The old MerchantPal routes (`/inventory/stock-in`, `/reports/profit`, `/insights`, `conversation_id`, no auth) are legacy and must not be used.

## Rules for the client

- The database is the source of truth. Never compute totals, debts, profit, stock or supplier rankings in the UI.
- Keep calls behind one small API client. The base URL is a config value so a phone can reach the laptop on the local network.
- JSON uses `snake_case`; amounts are NGN numbers formatted in the UI. Timestamps are ISO 8601.
- Errors share one shape: `{ "error": { "code": "...", "message": "..." } }`. Show failures as retryable, never as success.
- Trader endpoints need the session token from onboarding (`Authorization: Bearer <token>`). Store it on the device. A 401 sends the user back to onboarding.
- Send a client-generated `client_message_id` with each message so retries do not create duplicates.

## Planned endpoints

| Endpoint | Used by | Auth |
| --- | --- | --- |
| `POST /onboarding` | App | None, returns a session token |
| `GET /profile`, `PATCH /profile` | App | Session token |
| `POST /messages` (text or voice file) | App | Session token |
| `GET /entries` (filter by period and type, paged) | App, dashboard | Session token (app) |
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

Request and response shapes are frozen at the end of Sprint 0 and will be added here once they are. Until then, treat field names as provisional.

## Screens

Bottom navigation: Home, Assistant, Inventory, Profile.

- **Onboarding:** name, phone, business name, sector, market or area, main items with optional opening stock. One short step at a time, validated before submit.
- **Home:** profit and loss card (revenue, expenses, profit) with a today / 7 days / 30 days selector, total owed, "Items logged" newest first, and a restock suggestion card for low-stock items. Updates within 3 seconds of a new entry. Item detail shows `raw_text`.
- **Assistant:** type or record a voice note, send to `POST /messages`, show the one-line confirmation or clarifying question. Show a processing state for voice and a clear message when the backend or transcription is down.
- **Inventory:** items with quantity, unit, unit cost and low-stock highlight. Add or edit items, add opening stock, restock or adjust. "Where to restock" opens suggestions.
- **Profile:** edit name, business name, sector and location. List connected agents with scope, expiry and a Revoke button. Show the consent prompt (Approve or Reject) when a pending access request appears (poll).
- **Restock suggestions:** up to 3 suppliers with distance, unit price, rating, quality, quantity available and reason. Label them "Demo data".

## Dashboard (judges)

Entries newest first with `raw_text`, customers with balances and overdue flags, access requests with approved scopes, revocation status and access log. Updates within 3 seconds without a manual refresh. Demo controls: Reset and Seed.

## Agent action log

Agents working in this repo log their actions here.

- 2026-10-23: Rewrote README.md and this file for OJA. They described the old MerchantPal prototype (SQLite, `conversation_id`, no auth, `/reports/profit`).
  - Assumed the endpoint list and screens from final-prd.md sections 4 and 8. Field-level request and response shapes are not documented because the contract is not frozen.
  - Assumed "log your actions into FRONTEND_HANDOFF.md" meant this file. Earlier actions are in DANIEL_AGENT-ACTIONS.txt.
  - Not changed: `render.yaml`, `requirements.txt`, `backend.py/`, `eval/` (still MerchantPal).
