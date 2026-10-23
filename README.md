# OJA

Speak or type in Pidgin or English, and your books write themselves. OJA is a Flutter app for Lagos foodstuff traders (rice, beans, garri, oil) with a FastAPI backend, built for T.I.C Hackathon 3.0.

The AI interprets messages and phrases explanations. Totals, debts, profit, stock levels and supplier rankings are computed by the database and deterministic code.

Product requirements: [final-prd.md](final-prd.md). Agent rules: [AGENTS.md](AGENTS.md). Client contract: [FRONTEND_HANDOFF.md](FRONTEND_HANDOFF.md).

## Current OJA Status

The OJA backend is under `server/`. All server endpoints in [final-prd.md](final-prd.md) Section 8 are implemented: onboarding and profile, messages (text and voice), entries, customers, ask, home, inventory, suggestions, consent and agent summary. A judges' dashboard is served at `/dashboard`. The Flutter client is not in this repo yet.

```sh
cd server
poetry install
```

Copy the root `.env.example` to `.env` and configure variables used by `server/app/shared/env.py`. Never commit `.env` or place secrets in client code. Use PostgreSQL (`postgresql+psycopg://user:password@localhost:5432/oja`) or, for a laptop demo, SQLite (`sqlite:///./oja.sqlite3`). Tables and the synthetic supplier data are created on startup.

Run the API, from `server/`:

```sh
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000/dashboard`. With `DEMO_CONTROLS_ENABLED=true`, "Seed demo data" creates the demo trader (phone `08030000001`, Mama Ngozi and other customers with nicknames, starting stock) and puts its session token on the dashboard. The dashboard also has a lender agent screen and a trader console that stands in for the app.

Tables are created on startup but never altered. After pulling a change to the data model, delete the SQLite file (or reset the PostgreSQL database) and seed again.

Offline demo: set `DEMO_MODE=true` to skip every provider call. Extraction then uses the rule-based fallback, which also takes over automatically when the LLM call fails.

Evaluation (FR-S18), from the repository root:

```sh
PYTHONPATH=server python eval/run_eval.py --adapter app.ai.index:extract_message
```

## AI tools used (NFR-12)

- OpenAI API (`OJA_MODEL`, `OJA_STT_MODEL`) for extraction, name matching, intent routing, restock reason wording and speech-to-text.
- AI coding assistants: Claude Code (Anthropic). Team members add any others they used.

## Legacy Prototype

`backend.py/`, `eval/`, `requirements.txt`, `requirements-whisper.txt`, and `render.yaml` are the earlier OJA prototype. They are retained for reference and are not the OJA API contract. The existing Render service may still point at this prototype until deployment configuration is deliberately moved to the new `server/` application.

The prototype can be run from the repository root:

```sh
python -m pip install -r requirements.txt
uvicorn main:app --app-dir backend.py --reload
```

It contains earlier SQLite ledger, inventory, market price comparison, Whisper, and schema work. Follow [final-prd.md](final-prd.md) for current OJA behavior and priorities.
