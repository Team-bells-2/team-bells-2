# MerchantPal: MVP Product Requirements

PAU 24-Hour Hackathon · 23–24 Oct 2026

## Summary

MerchantPal helps small merchants record, understand, and act on their business information. Merchants describe what happened in everyday language; MerchantPal turns it into structured records and makes sales, expenses, stock, and estimated profit easier to see.

The MVP is merchant-first and starts in Nigeria. It should support a practical loop:

1. A merchant describes a sale, expense, or stock change by voice or text.
2. MerchantPal captures a structured record, asking a short clarification when important details are missing.
3. Sales and stock records update together where the sale involves a tracked item.
4. The merchant can inspect customer balances, stock on hand, sales, expenses, and estimated profit.

**One-line pitch:** "MerchantPal. Your business, understood."

## Problem and users

Small merchants are running real businesses with limited visibility. The problem is not a lack of effort; it is a lack of simple business information.

- **Sales and expenses are difficult to track consistently.** Business activity is spread across memory, notebooks, and informal messages.
- **Inventory is often managed manually.** Merchants may not have a current view of stock on hand or when to restock.
- **Profit is difficult to calculate accurately.** Sales totals alone do not show expenses or item costs.
- **Business decisions can become guesswork.** Useful information is hard to access while the merchant is busy running the business.

**Primary users:** Nigerian informal and small-scale merchants, starting with market traders, retailers, and small shop owners. The initial product should fit fast-moving sales and frequent stock changes without accounting complexity.

**Initial market:** Nigeria, with a path to learn locally before expanding to other African markets and wider markets.

Validate workflows with real merchants before treating assumptions about language, units, stock practices, or decision needs as settled.

## Theme fit

MerchantPal uses conversational AI to reduce the effort of turning business activity into usable records. Voice and plain language are input methods; saved records and transparent calculations remain the source of business totals.

| Prompt | What we show |
| --- | --- |
| MERCHANT FIRST | Simple records for Nigerian merchants, shaped around real trading workflows |
| CONVERSATIONAL | Voice and everyday language reduce forms and manual entry |
| BUSINESS VISIBILITY | Sales, expenses, stock, and estimated profit are organized into useful information |

**Why AI matters:** it can interpret natural descriptions, ask for missing details, and make business data easier to query. It must not invent totals; sales, balances, stock, and reports come from persisted records.

## Scope

Build a dependable first loop for merchants, keeping the workflow simple and the calculations auditable.

**In scope**

- Structured records for sales, credit sales, payments received, and expenses
- Inventory stock-in and on-hand quantity for tracked items
- Sales of tracked items reduce stock and record known cost of goods
- Customer balances derived from credit sales and recorded payments
- Date-bounded sales, expense, and estimated-profit reports
- Simple insights such as low-stock items and whether profit data is incomplete
- A conversational voice/text capture workflow in Pidgin and English; AI extraction and transcription are implemented as a separate layer
- A web dashboard for inspecting business information
- An evaluation set for message extraction and clarification behavior

**Out of scope**

- Automated forecasting and advanced financial advice
- Full accounting, tax, or audited profit reporting
- Real payments or real lender integrations
- Mobile app, sign-up and onboarding
- Yoruba, Hausa and Igbo (named as a next step)
- Pricing and business model
- Consent-gated lender-agent access in the first backend milestone; plan it as a later capability

## Features and requirements

MVP capabilities are prioritized around reliable capture and useful business visibility. AI interpretation must be able to ask rather than guess; reports must disclose missing cost data.

### F1. Capture business activity

The merchant provides a voice note or text description, and the system saves a structured record or asks one short question. The current backend accepts structured entries; transcription and AI extraction are a separate implementation step.

- Voice notes are transcribed to text, then the AI extracts an entry.
- Each entry has: `type` (sale, credit_sale, payment_received, expense), `item`, `quantity`, `unit`, `amount_ngn`, `customer`, `due_date`, `confidence`, `raw_text`.
- Naira shorthand is understood: "ten k" = 10,000, "2.5k" = 2,500.
- When a field is missing or unclear, the bot asks one question instead of guessing. Example: "I sell two bags and half" → "How much did you collect for the 2.5 bags?"
- Corrections update the last entry instead of adding a new one: "No, I mean four bags".
- Every entry is confirmed back in one line: "Recorded: credit sale, 2 bags rice, ₦60,000, Mama Ngozi, due Friday."

### F2. Sales, expenses, and customer balances

The backend stores merchant activity and calculates balances from recorded transactions.

- Name matching: "Mama Ngozi", "Ngozi" and "the rice woman" resolve to one customer. If unsure, the bot asks: "Is this the same Ngozi who bought rice on Monday?"
- Debts carry forward until a payment is recorded against them.
- Answers come from the database, not from the AI's guess. The AI may turn a question into a supported query.

### F3. Inventory tracking

- Merchants can record stock received with item, quantity, unit, and unit cost.
- The backend maintains on-hand quantity and a weighted average unit cost for repeated stock-ins.
- A sale of a tracked item reduces stock and records cost of goods atomically.
- The backend rejects a sale that would take tracked stock below zero.
- Items can have a reorder level; the system surfaces items at or below that level.

### F4. Profit visibility and simple insights

- Profit is estimated as recorded sales minus recorded expenses and known cost of goods.
- Sales without tracked item costs are counted and disclosed; the UI must not present the estimate as complete.
- Reports support a date range and insights can surface sales, estimated profit, and low-stock items.
- This is operational visibility, not audited accounting, forecasting, or financial advice.

### Later: voice/AI workflow and agent access

- AI extraction, clarification state, and correction handling are layered over the structured backend endpoints.
- Voice transcription is handled by a speech-to-text service.
- Consent-gated lender-agent access is planned after the core merchant workflow.

### Evaluation harness

A script runs Pidgin and English test sentences through the message interpretation workflow and reports a score with exact failures. Begin with the 12-case golden set in `eval/merchant_messages.json`; grow it toward 40 cases using real merchant phrasing and observed mistakes.

- Each test sentence has the expected entry or the expected clarifying question.
- Output: an overall pass count, category scores, and field-level failures showing expected and actual output.
- This is evaluation data, not model-training data. It does not teach the model Pidgin; the model/prompt interprets messages and this set checks whether it did so correctly.
- Add examples with merchant input and product-team review, especially when a real case fails or requires clarification.

## Architecture and API

One Python FastAPI backend sits in the middle and is the only component that touches the SQLite database. The dashboard and future conversational client use the API.

```
  Merchant (voice/text) --> AI capture layer --> FastAPI backend
                                                  |          |
                                               SQLite     Dashboard
                                      entries, customers, inventory, reports
```

The AI only reads and interprets messages. Totals, debts and answers come from the database, so numbers are never made up.

**Stack:** Python and FastAPI (the `backend.py/` folder), SQLite, a voice/text client, an LLM API for extraction and query interpretation, a speech-to-text API for voice notes, and a plain HTML dashboard.

| Endpoint | Used by | Does |
| --- | --- | --- |
| `POST /messages` | Telegram bot | Takes text or a transcribed voice note, returns a saved entry or a clarifying question |
| `GET /entries` | Dashboard | Lists ledger entries, newest first |
| `GET /customers` | Dashboard, bot | Lists customers with what each owes |
| `POST /ask` | Dashboard, bot | Currently answers "who owes me?" from the database |
| `POST /inventory/stock-in` | Dashboard, future bot | Adds stock and updates weighted unit cost |
| `GET /inventory` | Dashboard | Lists stock on hand and reorder levels |
| `GET /reports/profit` | Dashboard | Returns date-bounded sales, expenses, cost of goods, and estimated profit |
| `GET /insights` | Dashboard | Returns summary metrics and low-stock items |

Agent access endpoints remain a later phase and are not implemented in the current backend.

## Demo script and success criteria

The demo shows a merchant recording business activity and using the resulting information. Use a recorded backup if connectivity fails.

1. **Record a stock-in.** Add 10 bags of rice at a known unit cost. The inventory view shows quantity and cost.
2. **Record a sale.** Record a sale of 2 bags. The ledger shows the transaction and inventory falls by 2.
3. **Show customer debt.** Record a credit sale and a partial payment. The customer balance reflects the outstanding amount.
4. **Show profit visibility.** The report shows sales, expenses, known cost of goods, and estimated profit. An untracked sale is visibly counted as uncosted.
5. **Show a business insight.** The dashboard surfaces an item at or below its reorder level and supports the "Who owes me?" query.
6. **Show conversational capture when ready.** A Pidgin or English voice/text message is interpreted, clarified if needed, and saved through the structured backend.

**We call the build a success when:**

- [ ] Structured entries, customer balances, inventory, and profit report work against the API
- [ ] Stock is deducted atomically for tracked-item sales and cannot become negative
- [ ] Missing cost data is disclosed in the estimated-profit response and UI
- [ ] Conversational extraction is demoed if ready; otherwise the structured API flow is shown honestly
- [ ] The eval score is at least 30 of 40 once the interpretation harness is implemented, with failures listed honestly
- [ ] The repo is public, the README explains the build, and commits are spread across the 24 hours
- [ ] The backup demo video is recorded by 12 PM Saturday

## Team split and timeline

Four roles, one owner each. Names are open: fill them in when the team agrees.

| Role | Owns | Name |
| --- | --- | --- |
| AI + backend | Message extraction, clarifying questions, corrections, query interpretation | |
| Backend + data | API, database, customer balances, inventory, reports and insights | |
| Frontend | Merchant dashboard and conversational capture interface | |
| Product + pitch | 40 eval sentences, trader interviews, deck, backup video, pitch rehearsal | |

**Checkpoints (Friday 2 PM to Saturday 2 PM)**

1. **Friday 7 PM:** structured entry saved and returned by the API.
2. **Friday midnight:** inventory stock-in, tracked-item sale deduction, and customer debt checks working.
3. **Saturday 6 AM:** date-bounded profit report and low-stock insight working; uncosted sales clearly flagged.
4. **Saturday 10 AM:** conversational capture integration and first extraction evaluation, or a clear structured-entry fallback.
5. **Saturday 12 PM:** feature freeze. Final checks, backup video recorded, deck done.
6. **Saturday 1 PM:** pre-judging at our table. Demo on one laptop, backup on another.
7. **Saturday 2 PM:** submissions close. Submit the repo, deck PDF and video before 1:30 PM.
