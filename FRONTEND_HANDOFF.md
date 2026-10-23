# MerchantPal: Frontend Handoff

This is the frontend contract for the MerchantPal MVP. The FastAPI backend currently supports conversational text capture through a configured AI provider, structured business records, customer balances, inventory, and basic reporting. Voice transcription and lender-agent consent are future work.

## Product loop

A merchant records a sale, expense, payment, or stock-in. MerchantPal stores the record and calculates customer balances, stock on hand, and estimated profit from saved data. The database is the source of truth; do not derive authoritative totals in the UI or present incomplete profit as final.

## MVP screens

### Business overview and ledger

- Show sales, expenses, estimated profit, and the reporting period.
- List recent records newest first, with type, item, quantity/unit, amount, customer when relevant, due date, and recorded time.
- Clearly flag incomplete profit data when any sale has no known cost of goods.
- Provide loading, empty, and error states. Keep API failures distinct from empty data.

### Customers and balances

- Show customer name, current amount owed, and count of open credit sales.
- Use the backend balance; payments affect it only after the payment entry is saved.

### Inventory

- Show item, unit, quantity on hand, weighted average unit cost, and reorder level.
- Surface low-stock items from `/insights` or by comparing quantity against reorder level.
- Stock-in and tracked-item sales affect inventory on the backend. Do not optimistically calculate a second authoritative stock value in the UI.

### Conversational capture

The AI layer accepts merchant text and returns a saved entry, a clarification, or a correction. Voice transcription is not implemented; transcribe audio in the client before sending it to `/messages`.

## API conventions

- Configure the base URL, for example `http://localhost:8000`.
- JSON uses `snake_case`; NGN amounts are numbers. Format them for display in the frontend.
- Timestamps are ISO 8601. Due dates can currently be free-text values.
- There is no authentication or multi-merchant identity in the current demo backend.
- Routes below return JSON arrays for list resources, not object wrappers.

## Implemented endpoints

### `POST /messages`

Requires `OPENAI_API_KEY` on the backend. Send merchant text and a stable `conversation_id` so clarification and correction context remain isolated to the chat.

```json
{
  "text": "I give Mama Ngozi two bags rice on credit for 60k. She go pay Friday.",
  "conversation_id": "telegram-chat-123"
}
```

The response uses `status: "recorded"` with an `entry` or `action`, `status: "needs_clarification"` with `missing_fields` and `question`, or `status: "corrected"` with the updated entry. A correction updates the latest entry for that conversation rather than creating a duplicate. Provider failures return an error and should be shown as retryable, never as success.

### `GET /health`

```json
{ "status": "ok" }
```

### `POST /entries`

Creates a structured record and returns it with HTTP 201. Required: `type`, `amount_ngn`. `credit_sale` and `payment_received` also require `customer`. `type` is one of `sale`, `credit_sale`, `payment_received`, or `expense`.

Optional fields: `item`, `quantity`, `unit`, `customer`, `due_date`, `confidence`, and `raw_text`. The response adds `id`, `created_at`, and `cost_of_goods_ngn`.

```json
{
  "type": "sale",
  "item": "rice",
  "quantity": 2,
  "unit": "bags",
  "amount_ngn": 60000
}
```

If `item` matches tracked inventory, `quantity` and `unit` must match the tracked unit. The backend deducts stock and records cost of goods atomically. Insufficient stock returns HTTP 409. Untracked items remain allowed, with unknown cost.

### `GET /entries`

Returns a newest-first JSON array. Optional query parameters: `type`, `limit` (default 50, maximum 200), and `offset` (default 0).

```json
[
  {
    "id": 1,
    "type": "credit_sale",
    "item": "rice",
    "quantity": 2,
    "unit": "bags",
    "amount_ngn": 60000,
    "customer": "Mama Ngozi",
    "due_date": "Friday",
    "confidence": null,
    "raw_text": null,
    "cost_of_goods_ngn": null,
    "created_at": "2026-10-23T14:20:00+00:00"
  }
]
```

### `GET /customers`

Returns case-insensitive customer groups with balances calculated from credit sales and payments. `open_credit_sales` is a count, not a list of entry IDs.

```json
[
  { "name": "Mama Ngozi", "amount_owed_ngn": 30000, "open_credit_sales": 1 }
]
```

### `POST /ask`

Currently supports “Who owes me?” and “Who owes me money?” only. Other questions return HTTP 422 until the AI/query interpretation layer is added.

Request:

```json
{ "question": "Who owes me?" }
```

Response:

```json
{
  "answer": "Mama Ngozi owes you ₦30,000",
  "customers": [
    { "name": "Mama Ngozi", "amount_owed_ngn": 30000, "open_credit_sales": 1 }
  ]
}
```

### `POST /inventory/stock-in`

Adds stock, or adds to an existing item using a weighted average unit cost. Item units must remain consistent.

```json
{
  "item": "rice",
  "quantity": 10,
  "unit": "bags",
  "unit_cost_ngn": 20000,
  "reorder_level": 2
}
```

Returns the updated inventory item with HTTP 201.

### `GET /inventory`

Returns an array of items with `id`, `item`, `unit`, `quantity_on_hand`, `unit_cost_ngn`, `reorder_level`, and `updated_at`.

### `GET /reports/profit`

Optional `start_date` and `end_date` query parameters use `YYYY-MM-DD`. Defaults to the latest seven calendar days. Returns `sales_ngn`, `expenses_ngn`, `cost_of_goods_ngn`, `estimated_profit_ngn`, and `uncosted_sales_count`, plus the selected period. Profit is an estimate based on saved records and known stock costs, not audited accounting.

### `GET /insights`

Returns the default-period sales and estimated profit, whether profit is incomplete, the number of uncosted sales, and low-stock items.

## Not implemented yet

- `POST /messages`: conversational extraction, clarification, and corrections.
- Voice transcription.
- Natural-language queries beyond “Who owes me?”.
- Customer alias memory beyond case-insensitive exact-name grouping.
- Consent requests, lender summaries, and access revocation.

Keep calls behind a small API client so future features can be added without coupling screen components to transport details.
