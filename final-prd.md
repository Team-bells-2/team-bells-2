# OJA: Hackathon PRD

T.I.C Hackathon 3.0 | Fri 23 Oct 10:00 to Sat 24 Oct 10:00, 2026 | Living document for the PM's Kanban board

## 1\. Product summary

OJA lets a Lagos foodstuff trader speak or type in Pidgin or English in a Flutter mobile app and have the books write themselves. After a short onboarding that collects the trader's sector, the app gives them an assistant, a profile, an inventory, and a home page with profit and loss and every item logged. The system remembers customers and debts, suggests where to restock based on distance, customer reviews, quality, cost and quantity, and a lender's AI agent can see a scoped, totals-only summary after the trader approves.

**One-line pitch:** Speak in Pidgin, your books write themselves, and your business becomes something lenders can trust, with your permission.

**Design rule (non-negotiable):** the AI only interprets messages and phrases explanations. Totals, debts, profit, stock levels, supplier rankings and answers always come from the database and code, never from model output.

**Success for the 24 hours:** the 8-step demo runs live, the eval harness reports at least 30 of 40, and the demo survives a Wi-Fi failure.

## 2\. Assumptions and decisions to lock in the first hour

The project doc and the briefing disagree in places. Resolve these first, then update this table.

| # | Item | Working assumption | Owner |
| --- | --- | --- | --- |
| D1 | Deadline | Build window is 10:00 to 10:00. Submit by 09:30 Sat. The project doc's "Sat 2 PM submissions" and "12 PM freeze" are replaced by Section 10. Confirm in writing with organisers. | PM |
| D2 | Stack | Python + FastAPI, SQLite, a Flutter (Dart) client app for the trader, which replaces the earlier Telegram bot, and a plain HTML dashboard for judges. This overrides the earlier Postgres/Next.js default, because the project doc specifies SQLite and plain HTML. | Lead dev |
| D3 | LLM and speech-to-text providers | One provider each, chosen by free-tier limits and a Pidgin test of 5 voice clips. See Section 6. | AI dev |
| D4 | Demo trader and customers | One seeded trader, 4 to 5 customers (Mama Ngozi plus nicknames such as "the rice woman"), starting stock and seeded supplier data. The demo trader can be created live through onboarding or loaded by Seed. | PM + n8n teammate |
| D5 | Lender agent | A scripted agent (Python script or n8n workflow) plus a simple agent screen. Real lender integration is out of scope. | BE dev |
| D6 | Rules note | All code written inside the window. AI tools used are logged for the submission disclosure. | Everyone |
| D7 | Onboarding and sign-up | Onboarding collects name, phone, business name, sector (from a short fixed list), market or area, and main items sold with optional opening stock. No OTP or password: a session token is issued at sign-up. Only the Foodstuff sector is tuned and tested, other sectors are stored. | PM + BE |
| D8 | AI suggestions | Suggestions are restock suggestions. They rank suppliers for an item using distance, customer reviews, quality, cost and quantity available. Reviews are those left by other traders on suppliers. Supplier data and reviews are synthetic, seeded, and labelled as demo data. Confirm this reading in the first hour. | PM + AI |
| D9 | Demo device | An Android phone runs the Flutter app on the same local network or hotspot as the laptop that runs the backend. A spare phone and an emulator are the backup. iOS is not targeted. The phone screen is mirrored for the audience. | FE + QA |

## 3\. Users and scenarios

* **Primary user: Trader.** Foodstuff seller (rice, beans, garri, oil) who uses a smartphone daily, prefers voice, and mixes Pidgin, English and local words.
* **Secondary user: Lender agent.** An automated client (for example "QuickLoan agent") that needs a trustworthy, permissioned view of the business.
* **Judge/audience view: Dashboard.** A web page showing entries, debts and agent access in real time.

**Golden path (the demo, 8 steps):** (1) onboard as a new trader and choose a sector, (2) record a credit sale by voice, (3) clarify an ambiguous sale, (4) correct it, (5) record a payment against a nickname, (6) ask who owes, (7) see Home update with profit and loss and items logged, then see stock and a restock suggestion, and (8) approve a lender agent and see its summary.

## 4\. Functional requirements

Priority uses MoSCoW: **M** = must (golden path), **S** = should, **C** = could. If time runs short, cut F6 before F3, F3 before F2, and never cut F1. F5 is kept to its must-haves.

### 4.1 Server: capture and extraction (F1)

| ID | Requirement | Pri | Acceptance criteria |
| --- | --- | --- | --- |
| FR-S1 | POST /messages accepts text from the app for the signed-in trader and returns either a saved entry or a clarifying question. | M | Given a text message, when posted, then response has status of saved or clarify and a one-line confirmation string. |
| FR-S2 | Voice notes are transcribed to text before extraction (speech-to-text call), and the transcript is stored in raw_text. | M | Given an audio file recorded in the app, when posted, then a transcript is produced and extracted like text. On transcription failure the app asks the trader to resend or type. |
| FR-S3 | The LLM extracts a ledger entry matching the schema: type (sale, credit_sale, payment_received, expense), item, quantity, unit, amount_ngn, customer, due_date, confidence, raw_text. Output is validated against the schema (pydantic). | M | Invalid or malformed model output never reaches the database. One retry, then a clarifying question. |
| FR-S4 | Naira shorthand is normalised in code, not by the model: "ten k" = 10,000, "2.5k" = 2,500, "sixty k" = 60,000. | M | Unit tests cover at least 15 shorthand and word-number variants. |
| FR-S5 | When required fields are missing or confidence is below a threshold, the system asks exactly one short clarifying question and holds the pending entry. The next message completes it. | M | "I sell two bags and half" returns the question "How much did you collect for the 2.5 bags?". The answer completes and saves the entry. |
| FR-S6 | Corrections ("No, I mean four bags") update the last entry in place. The edit is recorded in an audit trail. | M | Given a saved entry, when a correction arrives, then the same entry ID is updated and the confirmation says so. |
| FR-S7 | Every saved entry is confirmed back in one line in the trader's register. | M | Confirmation matches the saved values, built from DB fields, not free model text. |
| FR-S8 | Unrecognisable or off-topic messages get a polite fallback, not a crash or a fabricated entry. | S | Gibberish input produces a fallback and no database write. |

### 4.2 Server: memory and queries (F2)

| ID | Requirement | Pri | Acceptance criteria |
| --- | --- | --- | --- |
| FR-S9 | Customers are stored with aliases. Name matching resolves "Ngozi" and "the rice woman" to Mama Ngozi using the alias table first, then the LLM against the existing customer list. | M | "The rice woman don pay thirty k" links to Mama Ngozi's record. Unsure matches ask "Do you mean Mama Ngozi?". |
| FR-S10 | Debts are computed from entries: credit sales add, payments received subtract, until paid. Balances are always derived, never hand-edited. | M | After a ₦60,000 credit sale and a ₦30,000 payment, Mama Ngozi's balance is ₦30,000. |
| FR-S11 | POST /ask turns a plain-language question into a fixed, parameterised query (a whitelist of intents such as who_owes, customer_balance, today_total, stock_level, restock_suggestion). The LLM picks the intent and parameters and never writes SQL. | M | "Who owes me?" returns debts from the database. Unknown intent returns a fallback. "Where I fit buy rice?" returns the restock suggestions from FR-S30. |
| FR-S12 | Overdue detection: entries past due_date are flagged in /customers and the assistant's answers. | C | Relative dates such as "Friday" resolve to a concrete date using the trader's current date. |

### 4.3 Server: consent-gated agent access (F3)

| ID | Requirement | Pri | Acceptance criteria |
| --- | --- | --- | --- |
| FR-S13 | POST /access-requests creates a pending request with agent_name, purpose and data_scopes. GET /access-requests?status=pending returns the signed-in trader's pending requests for the app. | M | Request without purpose or scopes is rejected with 422. |
| FR-S14 | POST /access-requests/{id}/approve (approve or reject, called by the app) issues a scoped token with expiry (30 days, shortened for demo). | M | Rejected requests issue no token. Tokens are random, stored hashed. |
| FR-S15 | GET /agent/summary returns totals only: sales total, number of active days, total owed. No customer names, no raw text, no entry IDs. | M | Response schema is an allow-list. A test asserts that no customer name from the database ever appears in the response. |
| FR-S16 | Every agent access is logged (agent, time, scope, result) and visible on the dashboard. | M | Calls with a valid, expired, revoked or missing token each produce the right status code and a log row. |
| FR-S17 | DELETE /access/{id} revokes access immediately. | M | The next /agent/summary call with that token returns 401 or 403. |

### 4.4 Server: evaluation harness (F4)

| ID | Requirement | Pri | Acceptance criteria |
| --- | --- | --- | --- |
| FR-S18 | A runnable script (make eval) runs 40 Pidgin and English sentences through the F1 pipeline and compares each to an expected entry or expected clarifying question. | M | Outputs "N of 40 correct" and a list of failures with expected versus got. |
| FR-S19 | The 40 sentences are stored in a version-controlled file. They are written inside the window, cover all four entry types, shorthand, nicknames, corrections and ambiguous cases, and include at least 10 that are hard on purpose. | M | Sentences are reviewed by someone other than the author. |
| FR-S20 | Eval results are exported to JSON for the deck, with failures listed honestly. | S | Target is at least 30 of 40. |

### 4.5 Server: onboarding, profile, inventory and home (F5)

| ID | Requirement | Pri | Acceptance criteria |
| --- | --- | --- | --- |
| FR-S21 | POST /onboarding creates a trader from name, phone, business name, sector, location (a market or area chosen from a seeded list) and main items sold, each with a unit and an optional opening quantity. It returns a session token. | M | A request missing name, phone, sector or location is rejected with 422. The token is random and stored hashed. Each item creates an inventory item, and an opening quantity creates an opening stock movement. |
| FR-S22 | GET /profile and PATCH /profile return and update the signed-in trader's name, business name, sector and location. | M | An update persists and shows on the next GET. A call without a valid token returns 401, and one trader's token never returns another trader's data. |
| FR-S23 | GET /inventory lists the trader's items (name, unit, quantity on hand, unit cost, reorder level, reorder quantity). POST /inventory adds an item and PATCH /inventory/{id} edits its details. | M | An item added in the app appears in the list. Editing details never changes quantity on hand. |
| FR-S24 | Stock changes are stock movements (opening, restock, adjustment) added with POST /inventory/{id}/stock. Quantity on hand is derived from the movements, never hand-edited. | M | After an opening stock of 10 bags and a restock of 5 bags, quantity on hand is 15 bags. An adjustment of -2 bags leaves 13. |
| FR-S25 | A saved sale or credit_sale whose item matches an inventory item creates a sale stock movement for its quantity. Matching uses the item name first, then the LLM against the trader's inventory list, in the same way as FR-S9. An item with no match is saved without a stock change and flagged "not in inventory". A sale larger than the stock on hand is still saved, and the item is flagged "check stock". | S | With 10 bags of rice in stock, a sale of 2.5 bags leaves 7.5 bags. A correction to 4 bags (FR-S6) updates the same movement and leaves 6 bags. |
| FR-S26 | A saved expense whose item matches an inventory item (for example, buying 5 bags of rice) creates a restock movement for its quantity. An expense with no matching item, such as transport, changes no stock. | S | After an expense for 5 bags of rice, stock rises by 5 bags and the expense counts in Home expenses (FR-S27). |
| FR-S27 | GET /home?period=today | 7d | 30d returns profit and loss for the period: revenue (sale and credit_sale amounts), expenses (expense amounts), profit (revenue minus expenses), total owed, the number of items logged and the items at or below their reorder level. All figures are computed from entries and stock movements in code. | M | Given a ₦50,000 sale, a ₦60,000 credit sale, a ₦30,000 payment received from that customer and a ₦40,000 expense: revenue is ₦110,000, expenses ₦40,000, profit ₦70,000 and total owed ₦30,000. Payments received are not revenue, because the credit sale already counted. A loss shows as a negative profit. A test proves model output cannot change these figures. |
| FR-S28 | GET /entries returns the trader's ledger entries newest first, with type, item, quantity, unit, amount, customer, due date, confidence, status and raw_text. It supports filtering by period and type, and paging. | M | A newly saved entry is the first item returned. Filtering by type returns only that type. |

### 4.6 Server: restock suggestions (F6)

| ID | Requirement | Pri | Acceptance criteria |
| --- | --- | --- | --- |
| FR-S29 | Supplier data is seeded as synthetic demo data: suppliers with an area and coordinates, offers per item (unit, unit price, quantity available, quality grade A, B or C) and reviews (rating 1 to 5 and a comment). | M | At least 4 suppliers offer each demo item (rice, beans, garri, oil), and each supplier has at least 3 reviews. The API and the app label the data as demo data. |
| FR-S30 | GET /suggestions?item=&quantity= ranks the suppliers that offer the item by a score from five factors: distance from the trader's location (computed in code), average review rating, quality grade, unit cost, and quantity available against quantity needed. Quantity defaults to the item's reorder quantity. Weights live in one config file, and the model never ranks. | M | The same data and request always return the same order. Fixture tests show that improving one factor of a supplier, with the rest unchanged, never lowers its rank, and that a supplier who cannot fill the quantity ranks below those who can. |
| FR-S31 | The response returns up to 3 suppliers, each with distance in km, unit price, average rating and review count, quality grade, quantity available and a one-line reason. The reason is wording only: the model phrases it from the factors, and every figure shown is read from the database. | M | Figures in the response match the database. If the model call fails, a template reason built from the top-scoring factors is returned instead. |
| FR-S32 | Suggestions appear where the trader needs them. An item at or below its reorder level gets a suggestion on Home and in Inventory, and the assistant answers "where I fit buy rice?" through the restock_suggestion intent (FR-S11). | M | Rice stock at or below its reorder level shows a top suggestion on Home. The assistant lists the same suppliers in the same order as GET /suggestions. |

### 4.7 Client: Flutter app (trader)

| ID | Requirement | Pri | Acceptance criteria |
| --- | --- | --- | --- |
| FR-C1 | The assistant screen lets the trader type or record a voice message, sends it to POST /messages, and shows the one-line confirmation or clarifying question in the chat. | M | Voice recording to confirmation round trip works on a phone. |
| FR-C2 | The app shows a "processing" indicator for voice notes, and a clear message if the backend or transcription is down. | S | No silent failures. |
| FR-C3 | The app shows the consent prompt ("QuickLoan agent wants to see your sales totals and debts for 30 days. Approve?") with Approve and Reject buttons whenever a pending access request is found, and confirms the outcome. | M | The prompt appears within 5 seconds of the request being created (polling). Tapping Approve calls the approve endpoint and shows confirmation. |
| FR-C4 | The assistant supports "who owes me?" style questions, and the Profile screen lists connected agents with a Revoke button. | M | Revoke from the app triggers DELETE /access/{id}. |
| FR-C5 | The app keeps the session token on the device, opens straight to Home for a signed-in trader, and returns to onboarding when the token is missing or rejected. | S | Reopening the app after onboarding lands on Home. A rejected token (401) sends the user back to onboarding. |
| FR-C12 | The onboarding flow collects name, phone, business name, sector, market or area, and main items sold with optional opening stock, one short step at a time. | M | A new trader completes onboarding in under 2 minutes and lands on Home. Required fields are validated before submit. The chosen sector is saved to the profile. |
| FR-C13 | The Home screen shows a profit and loss card (revenue, expenses, profit) with a period selector (today, 7 days, 30 days), the total owed, and "Items logged" listing entries newest first. | M | Figures match GET /home. A new entry from the assistant appears in Items logged and updates the profit and loss within 3 seconds of being saved, without a manual refresh. |
| FR-C14 | Each logged item opens to a detail view with type, item, quantity, amount, customer, due date, confidence and the transcript (raw_text). | S | The detail view shows raw_text, so the voice-to-ledger step is visible. |
| FR-C15 | The Inventory screen lists items with quantity on hand, unit, unit cost and a low-stock highlight, and lets the trader add an item, edit its details, and add opening stock, a restock or an adjustment. | M | A restock updates quantity on hand in the list straight away. Items at or below their reorder level are highlighted. |
| FR-C16 | The Profile screen shows and edits the trader's name, business name, sector and location, and lists connected agents with their scope and expiry (FR-C4). | M | An edit is saved and shown after reopening the app. Approved agents show their scope and expiry. |
| FR-C17 | Home shows a restock suggestion card for items at or below their reorder level, and each inventory item has a "Where to restock" action. Each suggestion shows supplier, distance, unit price, rating, quality, quantity available and the reason, labelled "Demo data". | M | Order and figures match GET /suggestions. |
| FR-C18 | Bottom navigation switches between Home, Assistant, Inventory and Profile. | M | All four screens are reachable in one tap from any screen. |

### 4.8 Client: dashboard and lender agent screen

| ID | Requirement | Pri | Acceptance criteria |
| --- | --- | --- | --- |
| FR-C6 | Dashboard lists ledger entries newest first, with type, item, quantity, amount, customer, due date and confidence. | M | A new entry appears within 3 seconds without a manual refresh (polling or server-sent events). |
| FR-C7 | Dashboard shows customers with balances, highlighting debts and overdue items. | M | Balances match GET /customers. |
| FR-C8 | Dashboard shows agent access requests, approved scopes, revocation status and the access log. | M | The consent flow is visible to judges. |
| FR-C9 | Lender agent screen shows the request step, the waiting state, and the totals-only credit-readiness summary once approved. | M | Screen works with the scripted agent, and shows an error state when access is revoked. |
| FR-C10 | Demo controls: "Reset demo data" and "Seed demo data" buttons or one command. | M | Reset returns to the clean starting state (no trader accounts, supplier and review data loaded). Seed adds the demo trader, customers and starting stock. Each finishes in under 10 seconds. |
| FR-C11 | Display the transcript next to each entry so judges can see the voice-to-ledger step. | S | Entry card shows raw_text. |

## 5\. Non-functional requirements

| ID | Category | Requirement |
| --- | --- | --- |
| NFR-1 | Correctness | Totals, balances, profit and loss, stock levels, supplier rankings and answers are computed from the database and code only. A test proves model output cannot change a total or a ranking. |
| NFR-2 | Performance | Text round trip under 5 seconds, voice round trip under 10 seconds on venue network. Dashboard update within 3 seconds. Home screen figures update within 3 seconds of a new entry, and suggestions return in under 5 seconds. |
| NFR-3 | Reliability | If the LLM or speech-to-text fails, the app says so and nothing is half-saved. All writes are atomic. |
| NFR-4 | Resilience | DEMO_MODE returns recorded responses for the golden path, including the restock-suggestion wording, when the network is down. A localhost-only run works with no internet, because the phone and laptop only need a shared local network. |
| NFR-5 | Idempotency | The same app message sent twice (for example a retry on a weak connection) must not create two entries (dedupe on a client-generated message ID). |
| NFR-6 | Privacy | Collect only what is needed. Agent tokens exclude customer names and profile data such as phone and location. Tokens are hashed, scoped and revocable. State data use in the deck, in line with the Nigeria Data Protection Act 2023. |
| NFR-7 | Security | No secrets in the repo, with .env.example provided. Secret scan in CI. Token-protected agent endpoints. Trader endpoints require the session token from onboarding, and each token reaches only that trader's data. CORS limited to the dashboard origin. |
| NFR-8 | Cost control | All LLM and speech calls go through one wrapper module with caching, timeouts, max_tokens and a call counter. |
| NFR-9 | Language | Pidgin and English in the assistant, and an English app interface. Yoruba, Hausa and Igbo are named as next steps only. |
| NFR-10 | Observability | Structured logs for every message (input, extracted entry, confidence, latency) so failures can be debugged and explained. |
| NFR-11 | Maintainability | One make entrypoint: setup, dev, check, seed, reset, eval, demo. Pinned versions (including Flutter) and a lockfile. make check runs the backend tests and Flutter analyze and test. |
| NFR-12 | Disclosure | AI coding tools and external APIs used are listed in the README for the submission. |
| NFR-13 | Mobile platform | The demo target is an Android phone running a release build from the tagged commit, with an emulator as backup. The API base URL is a config value so the phone can reach the laptop on the local network. iOS is not targeted. |

## 6\. Integrations

| Integration | Purpose | Notes and fallback |
| --- | --- | --- |
| Flutter client app (Dart) | Trader app (replaces Telegram) | An Android phone on the same local network or hotspot as the laptop that runs the backend. The API base URL is a config value. Voice recording asks for microphone permission on first use. Fallback: the emulator, a spare phone and the backup video. |
| LLM API | Extraction, name and item matching, intent routing, suggestion wording | Structured (JSON) output with schema validation. Test on Pidgin before choosing. Cached fixtures for CI and demo mode. |
| Speech-to-text API | Voice notes | The app records audio on the phone and uploads the file. Confirm the format the chosen provider accepts (for example M4A or WAV) and convert on the server if needed. Test 5 Pidgin clips early, since accuracy may be weak. Fallback: typed input and pre-recorded clips with known transcripts. |
| Lender agent (simulated) | Secondary user | Python script or n8n workflow calling the API. Keep a scripted fallback that replays the flow if the live call fails. |
| Supplier data (synthetic) | Restock suggestions | Seeded suppliers, offers, reviews and coordinates for Lagos areas, labelled as demo data in the API and the app. Distance is computed in code from the trader's chosen market or area, so no maps API is needed. |
| Cloudflare tunnel (optional) | Show the dashboard on judges' phones | Not required, since the briefing does not ask for hosting. Demo from the presenting laptop (backend and dashboard at localhost), with the phone app on the same local network and a second laptop as backup. |
| GitHub + Actions | Repo, CI | PR gate, secret scan, backend tests, Flutter analyze and test. Repo must be accessible to organisers and judges. |

## 7\. Data model (SQLite)

| Table | Key fields |
| --- | --- |
| traders | id, name, phone, business_name, sector, location_name, latitude, longitude, created_at |
| sessions | id, trader_id, token_hash, created_at, revoked_at |
| customers | id, trader_id, canonical_name, created_at |
| customer_aliases | id, customer_id, alias |
| entries | id, trader_id, customer_id (nullable), inventory_item_id (nullable), type, item, quantity, unit, amount_ngn, due_date, confidence, raw_text, status (pending, saved), created_at, updated_at |
| entry_edits | id, entry_id, old_values (JSON), new_values (JSON), edited_at |
| pending_clarifications | id, trader_id, partial_entry (JSON), question, created_at |
| inventory_items | id, trader_id, name, unit, unit_cost_ngn, reorder_level, reorder_quantity, created_at, updated_at |
| stock_movements | id, inventory_item_id, entry_id (nullable), quantity_change, reason (opening, restock, sale, adjustment), created_at |
| access_requests | id, trader_id, agent_name, purpose, scopes (JSON), status (pending, approved, rejected, revoked), requested_at, decided_at |
| access_tokens | id, request_id, token_hash, expires_at, revoked_at |
| access_log | id, request_id, endpoint, result, at |
| processed_messages | client_message_id (unique), trader_id, processed_at |
| suppliers | id, name, area, latitude, longitude, created_at (synthetic seed data) |
| supplier_offers | id, supplier_id, item, unit, unit_price_ngn, quantity_available, quality_grade (A, B, C), updated_at (synthetic seed data) |
| supplier_reviews | id, supplier_id, rating (1 to 5), comment, created_at (synthetic seed data) |

## 8\. API contract summary

The contract is frozen at the end of Sprint 0 (Section 9). Changes after that need QA and PM sign-off, because tests and clients depend on it.

| Endpoint | Called by | Auth |
| --- | --- | --- |
| POST /onboarding | App | None (creates the trader, returns a session token) |
| GET /profile, PATCH /profile | App | Trader session token |
| POST /messages | App | Trader session token |
| GET /entries | App, dashboard | Trader session token (app), none for the demo dashboard |
| GET /customers | App, dashboard | Trader session token (app), none for the demo dashboard |
| POST /ask | App | Trader session token |
| GET /home | App | Trader session token |
| GET /inventory, POST /inventory | App | Trader session token |
| PATCH /inventory/{id}, POST /inventory/{id}/stock | App | Trader session token |
| GET /suggestions | App | Trader session token |
| GET /access-requests | App | Trader session token |
| POST /access-requests | Lender agent | None (open request, no data returned) |
| POST /access-requests/{id}/approve | App | Trader session token |
| GET /agent/summary | Lender agent | Scoped bearer token |
| DELETE /access/{id} | App | Trader session token |
| GET /health | CI, smoke tests | None |

Errors share one shape: { "error": { "code": "...", "message": "..." } }.

## 9\. Roadmap and Kanban backlog

Columns: Todo, Doing, In Review, Done. One ticket in Doing per person. Tickets are 90 minutes or less, one branch each, PR linked to the ticket ID. Owners are role labels: **AI** (extraction and matching), **BE** (backend and data), **FE** (Flutter app and dashboard), **QA** (you, CI and tests), **PM**, **N8N**. Assign real names on the board.

### Sprint 0: Fri 10:00 to 11:30 (decide and scaffold)

| ID | Ticket | Owner | Pri | Est |
| --- | --- | --- | --- | --- |
| T-01 | Confirm deadline in writing, get submission link, resolve D1 to D9 | PM | M | 30m |
| T-02 | Create repo, folders, README, .gitattributes, .env.example, Makefile | QA | M | 45m |
| T-03 | Freeze ledger schema and API contract (Sections 4, 7, 8) | BE + AI | M | 60m |
| T-04 | Create LLM and speech-to-text keys, test one call each | AI | M | 30m |
| T-05 | CI pipeline: lint, typecheck, pytest, Flutter analyze and test, secret scan, branch protection | QA | M | 60m |
| T-06 | Kanban board, ticket template, working agreement posted | PM | M | 30m |
| T-45 | Create the Flutter app project, run it on a phone and an emulator, make the API base URL a config value | FE | M | 45m |

### Sprint 1: Fri 11:30 to 18:00 (walking skeleton, onboarding and F1 text)

| ID | Ticket | Owner | Pri | Est | Depends |
| --- | --- | --- | --- | --- | --- |
| T-07 | FastAPI skeleton, /health, SQLite models and migrations or init script | BE | M | 60m | T-03 |
| T-08 | LLM wrapper module (caching, timeout, budget, DEMO_MODE) | AI | M | 60m | T-04 |
| T-09 | Extraction prompt and pydantic validation (FR-S3) | AI | M | 90m | T-08 |
| T-10 | Naira shorthand normaliser and tests (FR-S4) | BE | M | 45m | T-07 |
| T-11 | POST /messages saves entry or asks clarifying question (FR-S1, S5, S7) | BE + AI | M | 90m | T-07, T-09 |
| T-12 | Flutter assistant screen: text loop (FR-C1) | FE | M | 60m | T-11, T-47 |
| T-13 | Dashboard entries list with live updates (FR-C6) | FE | M | 90m | T-07 |
| T-14 | Golden-path E2E skeleton: text sent as the app sends it, entry on dashboard (Playwright), plus one Flutter integration test of the assistant screen | QA | M | 90m | T-12, T-13 |
| T-15 | Write first 20 eval sentences with expected outputs (FR-S19) | PM + N8N | M | 90m | T-03 |
| T-16 | Seed and reset scripts for demo data (FR-C10) | N8N | M | 60m | T-07 |
| T-46 | Onboarding and profile endpoints, session token (FR-S21, S22) | BE | M | 60m | T-07 |
| T-47 | Flutter app shell with bottom navigation, onboarding flow and stored session (FR-C5, C12, C18) | FE | M | 90m | T-45, T-46 |

**18:00 checkpoint:** onboarding works in the app, a text message sent from the app is saved as an entry and shown on the dashboard, with E2E green in CI.

### Sprint 2: Fri 18:00 to Sat 00:00 (voice, clarify, correct, eval, Home and inventory)

| ID | Ticket | Owner | Pri | Est |
| --- | --- | --- | --- | --- |
| T-17 | Voice pipeline: record in the app, upload audio, transcribe, feed to extraction (FR-S2, C1) | AI + FE | M | 90m |
| T-18 | Corrections update last entry, audit trail (FR-S6) | BE | M | 60m |
| T-19 | Client message-ID dedupe and idempotency (NFR-5) | BE | S | 30m |
| T-20 | Eval harness runner and report (FR-S18, S20) | AI | M | 90m |
| T-21 | Remaining 20 eval sentences, peer-reviewed (FR-S19) | PM + N8N | M | 60m |
| T-22 | Test 5 Pidgin voice clips on speech-to-text, record accuracy, pick provider or fallback | AI + N8N | M | 45m |
| T-23 | Record 5 demo audio clips for the fallback | N8N | M | 30m |
| T-24 | Tests: shorthand, extraction contract with fixtures, correction flow, dedupe | QA | M | 90m |
| T-48 | Inventory items and stock movements, with sale and restock effects (FR-S23 to S26) | BE | M | 90m |
| T-49 | Home summary with profit and loss, and the entries list endpoint (FR-S27, S28) | BE | M | 60m |
| T-50 | Flutter Home: profit and loss card with period selector, items logged, item detail (FR-C13, C14) | FE | M | 90m |
| T-51 | Flutter Inventory screen (FR-C15) | FE | M | 90m |
| T-52 | Flutter Profile screen (FR-C16) | FE | M | 60m |

**Midnight checkpoint (20:00 to 20:30 dinner, 22:00 readiness check):** voice, clarify and corrections work in the app, Home shows profit and loss and items logged, and inventory works. First eval score recorded. Repo, deck outline and demo plan confirmed on track.

### Sprint 3: Sat 00:00 to 06:30 (quiet hours: memory, queries, consent, suggestions). Everyone sleeps at least 3 hours, in shifts

| ID | Ticket | Owner | Pri | Est |
| --- | --- | --- | --- | --- |
| T-25 | Customers, aliases and name matching (FR-S9) | AI + BE | M | 90m |
| T-26 | Debt calculation and GET /customers (FR-S10, C7) | BE | M | 60m |
| T-27 | POST /ask intent whitelist and parameterised queries (FR-S11) | AI + BE | M | 90m |
| T-28 | Access request, approve, token issue, revoke endpoints (FR-S13, S14, S17) | BE | M | 90m |
| T-29 | GET /agent/summary allow-list schema and access log (FR-S15, S16) | BE | M | 60m |
| T-30 | App consent prompt with Approve and Reject, and a Revoke button in Profile (FR-C3, C4) | FE | M | 60m |
| T-31 | Dashboard: customers, access requests and log, agent screen (FR-C7, C8, C9) | FE | M | 90m |
| T-32 | Scripted lender agent (script or n8n) and fallback replay | N8N | M | 60m |
| T-33 | Security tests: token scopes, no customer names or profile data in summary, revoked and expired tokens, session-token authz, no cross-trader reads | QA | M | 90m |
| T-34 | Full golden-path E2E for all 8 demo steps with fixtures | QA | M | 90m |
| T-53 | Seed suppliers, offers and reviews as synthetic data (FR-S29) | N8N | M | 60m |
| T-54 | Ranking engine and GET /suggestions (FR-S30, S31) | BE | M | 90m |
| T-55 | Suggestion wording with template fallback, and the restock_suggestion intent in /ask (FR-S31, S32, S11) | AI | M | 60m |
| T-56 | Flutter restock suggestions on Home and in Inventory (FR-C17) | FE | M | 90m |
| T-57 | Tests: profit and loss, stock derivation, ranking order, onboarding and token isolation | QA | M | 90m |

**Feature freeze: around 04:00 to 06:30.** Cut F6 polish, then F3 polish, before F2. After freeze it is bug fixes only.

### Sprint 4: Sat 06:30 to 09:30 (harden, record, submit)

| ID | Ticket | Owner | Pri | Est |
| --- | --- | --- | --- | --- |
| T-35 | Exploratory QA on phone and browser, bugs filed as tickets | N8N | M | ongoing |
| T-36 | Bug fixes from QA, eval failures reviewed (fix cheap ones, list the rest honestly) | AI + BE + FE | M | ongoing |
| T-37 | README: setup, architecture, AI tools used, synthetic data and limits | QA + PM | M | 30m |
| T-38 | Pitch deck PDF: problem, demo, architecture, eval score, consent model, next steps | PM | M | 90m |
| T-39 | Code freeze at 08:30, tag v1-demo, demo laptop pulls tag, spare laptop cloned, release APK built from the tag and installed on the demo phone and a spare phone | QA | M | 30m |
| T-40 | Record backup video from the tagged build | PM + FE | M | 30m |
| T-41 | Rehearse pitch twice, including Wi-Fi-down and DEMO_MODE run | PM + all | M | 30m |
| T-42 | Submit repo link, demo, deck by 09:30 (30-minute buffer before 10:00) | PM | M | 15m |

### After submission (Sat 10:00 to 14:00)

| ID | Ticket | Owner |
| --- | --- | --- |
| T-43 | AV check, adapters, phone screen mirroring tested, demo laptop on power, tunnel optional | QA + PM |
| T-44 | Pitch (about 5 minutes plus about 3 minutes of questions), judging and networking | PM + presenter |

## 10\. Milestone summary

| Time | Milestone | Gate |
| --- | --- | --- |
| Fri 11:30 | Sprint 0 done | Contract frozen, CI green on an empty app, Flutter app runs on a phone |
| Fri 18:00 | Onboarding, text in, entry saved, dashboard live | E2E green |
| Fri 22:00 | Readiness checkpoint | Repo, demo and deck on track |
| Sat 00:00 | Voice, clarify, correct, Home, inventory, first eval score | Voice round trip on a phone, Home shows profit and loss |
| Sat 04:00 to 06:30 | Memory, debts, ask, consent, suggestions | Full 8-step E2E green |
| Sat 06:30 | Feature freeze | Bug fixes only |
| Sat 08:30 | Code freeze, v1-demo tag | Nothing new ships |
| Sat 09:30 | Submit | Repo, deck, demo link accepted |
| Sat 10:00 | Window closes | Commits after this are not counted |

## 11\. Definition of done (per ticket)

* Merged to main through a PR, CI green, linked to the ticket ID.
* Acceptance criteria demonstrated on the demo laptop, and on the demo phone for app tickets.
* Touches only the owner's folders (backend/app/ai/, backend/app/ledger/, backend/app/consent/, backend/app/inventory/, backend/app/suggestions/, app/, dashboard/, eval/, automation/, docs/).
* A test exists for any behaviour on the golden path.
* New environment variables are in .env.example.

## 12\. Test priorities (QA)

1. **Golden-path E2E** for the 8 demo steps, using fixtures instead of live LLM calls. The API steps run in the test suite, the dashboard steps in Playwright and the app screens in Flutter integration tests.
2. **Consent and privacy tests:** no customer names in /agent/summary, scopes enforced, expired and revoked tokens rejected, tokens never stored in plain text, no profile data (phone, location) in the summary, and one trader's session token cannot read another trader's data.
3. **Correctness tests:** debts derive correctly from entries, profit and loss matches the entries, stock on hand derives from movements, supplier ranking is stable and responds to each factor, shorthand normalisation, corrections update in place (including stock), dedupe works.
4. **Extraction contract tests:** invalid model output never reaches the database.
5. **Resilience tests:** LLM or speech failure produces a clear app message and no partial write.
6. **Eval harness** run in CI on fixtures, and live before the freeze.
7. **App tests:** Flutter widget and integration tests for onboarding, the assistant screen, Home and the consent prompt.

## 13\. Risks and mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Speech-to-text handles Pidgin poorly | Voice demo fails | Test early (T-22), keep typed input and pre-recorded clips with known transcripts, show transcript on screen |
| Free-tier LLM or speech limits hit | Build stalls or demo fails | Wrapper with caching and fixtures, one provider chosen early, DEMO_MODE |
| Venue Wi-Fi is unreliable | Live demo fails | Phone hotspot, localhost demo, recorded backup video |
| Phone cannot reach the backend | App unusable in the demo | Phone and laptop on one hotspot or local network, backend bound to the LAN address, base URL in config, spare phone and emulator, recorded backup video |
| Model fabricates numbers | Trust lost | Design rule: DB is the source of truth, confirmations built from saved fields |
| Name matching wrong | Wrong debt linked | Ask when unsure, alias table first, tested with nickname cases |
| Scope creep | Golden path unfinished | PM owns cuts: F6 first, then F3 polish, before F2. F5 is kept to its must-haves. Nothing new after the freeze |
| Flutter setup or device problems | App not running on a phone | Scaffold and run on a phone in Sprint 0 (T-45), keep an emulator and a release APK from the tagged build |
| Suggestions look arbitrary or rest on synthetic data | Weak trust in recommendations | Deterministic ranking in code, factors shown on screen, supplier data labelled as demo data, real supplier data named as a next step |
| Eval score below 30 | Weak technical story | Report honestly with a failure list and next steps, as the project doc intends |
| Merge conflicts and agent mistakes | Lost hours | Folder ownership, small PRs, CODEOWNERS, AGENTS.md, review every diff |

## 14\. Out of scope

Sector-specific tuning beyond foodstuff (other sectors are stored at onboarding but not tuned or tested), custom ledgers, detailed accounting (cost of goods, tax, balance sheet), insights beyond restock suggestions, iOS and web builds of the app, push notifications, offline mode, phone verification and password recovery, real supplier data and live prices, ordering from or paying suppliers, writing supplier reviews in the app, real payments, real lender integrations, Yoruba, Hausa and Igbo, pricing and business model. Name these as next steps in the deck.
