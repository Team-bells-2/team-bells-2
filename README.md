# OJA

Speak or type in Pidgin or English, and your books write themselves. OJA is a Flutter app for Lagos foodstuff traders (rice, beans, garri, oil) with a FastAPI backend, built for T.I.C Hackathon 3.0.

The AI interprets messages and phrases explanations. Totals, debts, profit, stock levels and supplier rankings are computed by the database and deterministic code.

- Product requirements: [final-prd.md](final-prd.md)
- Agent rules: [AGENTS.md](AGENTS.md)
- API contract for the app: [FRONTEND_HANDOFF.md](FRONTEND_HANDOFF.md)
- Backend architecture: [server/app/info.md](server/app/info.md)
- Work plan: [server/IMPLEMENTATION_PLAN.md](server/IMPLEMENTATION_PLAN.md)

## Repository layout

| Path | What it is |
| --- | --- |
| `server/` | The OJA backend (FastAPI, SQLAlchemy, PostgreSQL, Alembic), vertical slices under `server/app/` |
| `client/` | The Flutter app (not yet calling the API) |
| `backend.py/`, `eval/`, `render.yaml`, `requirements-whisper.txt` | Earlier prototype, kept for reference. Not the OJA API contract |
| `alembic.ini` | Alembic config; migrations live in `server/app/shared/Infrastructure/db/alembic/` |
| `requirements.txt` | Python dependencies for `server/` |

## Status

Live: onboarding (with main items), profile, messages (text and voice), entries, customers (aliases, balances, overdue), inventory (read and write), home (with restock cards), restock suggestions, `/ask`, consent and the lender agent summary.
Not yet: offline `DEMO_MODE`, demo reset and the judges' dashboard, CORS, session expiry. See [server/IMPLEMENTATION_PLAN.md](server/IMPLEMENTATION_PLAN.md).

## Set up and run the backend

Needs Python 3.12+ and PostgreSQL. From the repository root:

```sh
python -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env            # then fill in DATABASE_URL, LLM_API_KEY and the rest
.venv/bin/alembic upgrade head  # create or update the tables
cd server
../.venv/bin/python -m app.demo.index   # seed locations and demo suppliers (safe to rerun)
../.venv/bin/uvicorn app.main:app --reload --port 8000
```

- API docs: <http://127.0.0.1:8000/docs>
- Every setting is required and read from `.env` (see `.env.example`). A missing key stops startup with its name.
- Never commit `.env` or put secrets in client code.
- Voice notes are transcribed by any OpenAI-compatible endpoint set in `STT_*`. For a local whisper.cpp server, start it with `--convert` (needs ffmpeg) so it accepts M4A as well as WAV.

## Database changes

Tables change only through Alembic. After editing models, from the repository root:

```sh
.venv/bin/alembic revision --autogenerate -m "describe the change"
.venv/bin/alembic upgrade head
.venv/bin/alembic check          # "No new upgrade operations detected." means models and database agree
```

Never edit a migration that is already merged.

## Make targets

From the repository root: `make setup`, `make migrate`, `make seed`, `make dev`, `make test`, `make eval` (offline) and `make eval-live` (uses the LLM in `.env`). `make help` lists them.

## Eval harness (FR-S18 to S20)

`server/eval/cases.json` holds 40 Pidgin and English messages (all four entry types, shorthand, nicknames, corrections, clarifying questions; 10 marked hard) with the expected entry or question. `make eval` runs each through `POST /messages` on a fresh in-memory database with the demo trader, prints "N of 40 correct" with expected versus got, and writes `server/eval/results.json`. The cases still need review by someone other than their author (FR-S19).

## Tests

```sh
cd server
../.venv/bin/python -m unittest discover -s tests -t .
```

The tests use an in-memory SQLite database, a fake LLM and a fake speech-to-text provider, so they need no API key and no network. GitHub Actions (`.github/workflows/backend-tests.yml`) runs on pushes to `oja` and pull requests into `oja` or `main` that touch the backend, in two jobs: the tests on SQLite, and a PostgreSQL 16 job that runs the migrations (upgrade, `alembic check`, full downgrade and back), the seed twice, the same tests on Postgres, and `server/e2e/smoke.py` against a running server in `DEMO_MODE`. Neither job needs secrets or calls a provider.

`server/e2e/smoke.py` can also be run by hand against any server started with `DEMO_CONTROLS_ENABLED=true` (it resets the demo data): `cd server && ../.venv/bin/python -m e2e.smoke --base-url http://127.0.0.1:8000`. Add `--voice clip.m4a` (repeatable) to send recorded voice notes through the server's speech-to-text. To run them against PostgreSQL, set `TEST_DATABASE_URL` to a throwaway database: its tables are dropped and recreated for every test.

## AI tools used (NFR-12)

- LLM through an OpenAI-compatible endpoint (`LLM_MODEL`): message interpretation and restock reason wording. Amounts, totals and rankings are computed in code.
- Speech-to-text through an OpenAI-compatible endpoint (`STT_MODEL`), locally whisper.cpp.
- AI coding assistants: Claude Code (Anthropic). Team members add any others they used.

## Prototype

`backend.py/` is an earlier single-merchant prototype (SQLite, market price comparison, local Whisper). It is kept for reference only. `render.yaml` still deploys it, until deployment is moved to `server/`. To run it:

```sh
.venv/bin/uvicorn main:app --app-dir backend.py --reload
```

It reads `OPENAI_API_KEY`, `OPENAI_BASE_URL` and `OJA_MODEL` (see the prototype block in `.env.example`).
