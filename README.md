# MerchantPal

## Backend

The FastAPI backend uses SQLite for merchant records, inventory, and reports. From the project root:

```sh
python -m pip install -r requirements.txt
cp .env.example .env
# Open .env and replace the empty OPENAI_API_KEY value with your provider key
uvicorn main:app --app-dir backend.py --reload
```

The API is available at `http://127.0.0.1:8000`; interactive endpoint docs are at `/docs`. Put your key in the root `.env` file under `OPENAI_API_KEY`. The app loads it when it starts. Never commit `.env` or share the key in chat. `OPENAI_BASE_URL` can point to an OpenAI-compatible provider, and `MERCHANTPAL_MODEL` selects the model (default `gpt-4o-mini`). Set `SABIMARKET_DB_PATH` to choose a different SQLite file.

### Current endpoints

- `GET /health`: process health check.
- `POST /messages`: interprets merchant text with the configured model, asks clarification when needed, saves extracted records, and applies corrections to the latest entry in that conversation. Send a stable `conversation_id` per merchant/chat.
- `POST /entries` and `GET /entries`: create and list sales, credit sales, payments, and expenses. Listing supports `type`, `limit`, and `offset` query parameters.
- `GET /customers`: customer balances calculated from credit sales and recorded payments.
- `POST /ask`: answers the deterministic “Who owes me?” query from saved records. Other natural-language questions are not implemented yet.
- `POST /inventory/stock-in`: add stock and unit cost; repeated stock-ins update the weighted average unit cost.
- `GET /inventory`: list stock on hand and reorder levels.
- `GET /reports/profit`: summarize sales, expenses, and known cost of goods for a date range (`start_date` and `end_date`, both `YYYY-MM-DD`). Defaults to the last seven days.
- `GET /insights`: returns the default-period business summary and items at or below their reorder level.

Sales for a tracked item deduct inventory and capture cost of goods in the same database transaction. Sales for untracked items are allowed, but profit reports count them as uncosted and flag that estimated profit is incomplete. Profit is an estimate based on recorded entries and stock costs, not a replacement for verified accounting.

Voice transcription and access-consent routes are not implemented yet. `/messages` accepts text; transcribe voice messages in the client before sending them.

## Message evaluation

`eval/merchant_messages.json` contains 12 representative Pidgin and English cases for the extractor. These examples do not train the AI; they check its output and report exact field-level failures. Validate the set with:

```sh
python eval/run_eval.py --validate-only
```

Run the evaluation against the configured model with `python eval/run_eval.py --adapter ai_extractor:extract_message`. This makes provider calls and requires `OPENAI_API_KEY`. Grow the set using phrases and edge cases gathered from real merchants, not just synthetic variations.

Run the backend checks with:

```sh
python -m unittest discover -s backend.py -p 'test_*.py'
```

## Deploy to Render

The repository includes a `render.yaml` Blueprint for the FastAPI API. Push the project to GitHub, create a new Blueprint in Render, and select this repository. During Blueprint setup, enter `OPENAI_API_KEY` when Render prompts for the secret; do not put the key in `render.yaml` or GitHub.

The Blueprint mounts a persistent disk at `/var/data` for SQLite. Render persistent disks require a paid service plan. If using a free instance instead, move persistence to a managed PostgreSQL database before relying on stored merchant records, because the instance filesystem is not durable across deploys.

After deployment, check `https://<your-render-service>.onrender.com/health`; API docs are at `/docs` on the same host.