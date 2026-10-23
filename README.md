# OJA

Speak or type in Pidgin or English, and your books write themselves. OJA is a Flutter app for Lagos foodstuff traders (rice, beans, garri, oil) with a FastAPI backend, built for T.I.C Hackathon 3.0.

The AI interprets messages and phrases explanations. Totals, debts, profit, stock levels and supplier rankings are computed by the database and deterministic code.

Product requirements: [final-prd.md](final-prd.md). Agent rules: [AGENTS.md](AGENTS.md). Client contract: [FRONTEND_HANDOFF.md](FRONTEND_HANDOFF.md).

## Current OJA Status

The new OJA backend is under `server/`. It currently contains database configuration/session scaffolding and vertical-slice placeholders. The OJA API endpoints and Flutter client are not implemented yet. Dependencies are managed with Poetry in `server/`.

```sh
cd server
poetry install
```

Copy the root `.env.example` to `.env` and configure variables used by `server/app/shared/env.py`. Never commit `.env` or place secrets in client code. The planned database is PostgreSQL; an example SQLAlchemy URL is `postgresql+psycopg://user:password@localhost:5432/oja`.

## Legacy MerchantPal Prototype

`backend.py/`, `eval/`, `requirements.txt`, `requirements-whisper.txt`, and `render.yaml` are the earlier MerchantPal prototype. They are retained for reference and are not the OJA API contract. The existing Render service may still point at this prototype until deployment configuration is deliberately moved to the new `server/` application.

The prototype can be run from the repository root:

```sh
python -m pip install -r requirements.txt
uvicorn main:app --app-dir backend.py --reload
```

It contains earlier SQLite ledger, inventory, market price comparison, Whisper, and schema work. Follow [final-prd.md](final-prd.md) for current OJA behavior and priorities.
