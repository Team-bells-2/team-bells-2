# Run the backend workflow locally from the CLI

This runbook reproduces the backend jobs in [backend-tests.yml](../../.github/workflows/backend-tests.yml) without GitHub Actions. It excludes Flutter. Run commands from the repository root unless a step says to change directory.

## What this runs

1. The SQLite `unittest` suite.
2. The PostgreSQL workflow: migrate, check schema drift, downgrade and re-upgrade, seed twice, run the suite against a separate test database, then run the black-box HTTP/WebSocket smoke against a migrated PostgreSQL app database in `DEMO_MODE`.
3. Optionally, the offline eval harness and a real STT clip upload.

These commands use fake providers for unit tests and offline rules for the smoke test. They do not call the live LLM or STT unless you explicitly run `make eval-live` or pass an audio clip to the smoke command.

## Safety and prerequisites

- Use a local PostgreSQL instance and **two new, throwaway databases**: one for migrations and the running API, and another for tests.
- The test fixture drops and recreates its mapped tables. Never point `TEST_DATABASE_URL` at a database with useful data, or use the app database for the tests.
- The smoke script calls `/demo/reset`, which deletes trader data in the configured API database. Never point it at a shared or production database.
- Do not overwrite an existing `.env`. It contains local settings and possibly secrets; keep credentials out of shell transcripts and reports.
- Required tools: Python 3.12 (the workflow version), Git, PostgreSQL client `psql`, and a running PostgreSQL 16 server. Docker is optional if you already have PostgreSQL available.
- Commands below use `postgresql+psycopg` as in the project configuration. Substitute local role, password, host, port, and unique database names as appropriate.

## 1. Prepare Python and dependencies

Check the Python version used for this run:

```sh
python3.12 --version
```

The GitHub workflow uses Python 3.12. If you want to reproduce it exactly and do not already have a Python 3.12 virtual environment, create one without replacing `.venv`:

```sh
python3.12 -m venv .venv-ci
.venv-ci/bin/python -m pip install -r requirements.txt
```

For the remaining commands, set `PYTHON` and `ALEMBIC` to the chosen environment. Use the existing `.venv` if preferred:

```sh
export PYTHON="$PWD/.venv-ci/bin/python"
export ALEMBIC="$PWD/.venv-ci/bin/alembic"
```

If using `.venv`, change both paths to `$PWD/.venv/bin/python` and `$PWD/.venv/bin/alembic`. If packages are not installed in that environment, install them with:

```sh
"$PYTHON" -m pip install -r requirements.txt
```

Confirm a root `.env` exists and contains all settings required by the app. CI copies `.env.example` because CI supplies the database URLs through the process environment; do not copy it over your local `.env`.

## 2. Run the SQLite job

From the repository root:

```sh
cd server
../.venv/bin/python -m unittest discover -s tests -t .
cd ..
```

If you chose `.venv-ci`, use `../.venv-ci/bin/python` instead.

**Pass:** unittest exits with status 0 and reports `OK`. The suite uses in-memory SQLite and provider fakes. No PostgreSQL, API key, or network provider call is needed for this job.

The voice upload-limit test assumes the test fixture's 1 MiB limit. If your shell already exports `STT_MAX_UPLOAD_MB` with a different value, pin the test setting explicitly for this command:

```sh
cd server
STT_MAX_UPLOAD_MB=1 ../.venv/bin/python -m unittest discover -s tests -t .
cd ..
```

Use `../.venv-ci/bin/python` instead if running in `.venv-ci`. The CI job starts with a clean environment and the test fixture supplies this value by default.

## 3. Create two isolated PostgreSQL databases

Use unique names for this run. Do not drop an existing database. The following examples match the CI job's separate app/test databases, with unique local suffixes:

```sh
export E2E_APP_DB="oja_cli_app_$(date +%Y%m%d_%H%M%S)"
export E2E_TEST_DB="oja_cli_test_$(date +%Y%m%d_%H%M%S)"
```

Create each database using a PostgreSQL role with `CREATEDB`. For a local PostgreSQL accepting the current OS user:

```sh
createdb "$E2E_APP_DB"
createdb "$E2E_TEST_DB"
```

Or, when password authentication is required, connect using your local PostgreSQL credential method:

```sh
psql -h 127.0.0.1 -U <role> -d postgres -c "CREATE DATABASE $E2E_APP_DB"
psql -h 127.0.0.1 -U <role> -d postgres -c "CREATE DATABASE $E2E_TEST_DB"
```

Do not put a password directly in a command. Use a local `.pgpass`, prompt, or another approved local credential method. If either create command says the database already exists, stop and choose a different name rather than reusing it.

Set the app database for migrations/server and the separate test database for the test fixture:

```sh
export DATABASE_URL="postgresql+psycopg://<role>:<password>@127.0.0.1:5432/$E2E_APP_DB"
export TEST_DATABASE_URL="postgresql+psycopg://<role>:<password>@127.0.0.1:5432/$E2E_TEST_DB"
```

Use a local shell prompt or environment manager for credentials. Do not save literal credentials in this file, Git, or copied terminal output. Confirm the URLs name different databases before proceeding.

## 4. Reproduce the PostgreSQL migration job

From the repository root, with `DATABASE_URL` set to the new app database:

```sh
"$ALEMBIC" upgrade head
"$ALEMBIC" check
"$ALEMBIC" downgrade base
"$ALEMBIC" upgrade head
```

**Pass:** all commands exit 0, and `alembic check` says `No new upgrade operations detected.` The downgrade is deliberately run only against the throwaway app database.

## 5. Reproduce reference seeding

The workflow seeds reference locations/suppliers twice to check rerun safety. Run:

```sh
cd server
"$PYTHON" -m app.demo.index
"$PYTHON" -m app.demo.index
cd ..
```

**Pass:** both commands exit 0.

## 6. Run the PostgreSQL backend suite

Keep `DATABASE_URL` pointed at the app database and `TEST_DATABASE_URL` pointed at the separate test database. Run:

```sh
cd server
../.venv/bin/python -m unittest discover -s tests -t .
cd ..
```

If using `.venv-ci`, replace `../.venv/bin/python` with `../.venv-ci/bin/python`.

**Pass:** unittest exits 0 and reports `OK`. This run may drop/recreate tables in `E2E_TEST_DB`; it must not affect `E2E_APP_DB`.

## 7. Run the live-server E2E smoke

The smoke requires the migrated **app** database, `DEMO_CONTROLS_ENABLED=true`, and offline `DEMO_MODE=true`. It resets demo trader data, seeds the demo trader, then tests HTTP and WebSocket flows. Do not run the PostgreSQL test suite concurrently with this server.

In terminal A, from the repository root:

```sh
export DATABASE_URL="postgresql+psycopg://<role>:<password>@127.0.0.1:5432/$E2E_APP_DB"
export DEMO_MODE=true
export DEMO_CONTROLS_ENABLED=true
cd server
../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

If using `.venv-ci`, replace `../.venv/bin/uvicorn` with `../.venv-ci/bin/uvicorn`.

In terminal B, from the repository root, point `DATABASE_URL` to that same app database, enable demo controls, then check readiness and run smoke:

```sh
export E2E_APP_DB='paste-the-same-app-database-name-used-in-terminal-A'
export DATABASE_URL="postgresql+psycopg://<role>:<password>@127.0.0.1:5432/$E2E_APP_DB"
export DEMO_CONTROLS_ENABLED=true
curl --fail --show-error http://127.0.0.1:8000/health
cd server
../.venv/bin/python -m e2e.smoke --base-url http://127.0.0.1:8000
```

If using `.venv-ci`, replace `../.venv/bin/python` with `../.venv-ci/bin/python`.

**Pass:** the command prints `smoke passed` and exits 0. It covers health, reset/seed, WebSocket ping/event/close, sales, due date, nickname payment, clarification, derived stock/customer/Home figures, `/ask`, suggestions, consent approval and summary, logout, and rejection of an old token.

When finished, stop Uvicorn with Ctrl+C in terminal A. Do not add `--reload` or run multiple workers for the WebSocket smoke.

## 8. Optional evaluation and real audio

Run the offline evaluation from the repository root:

```sh
make eval
```

It reports the score and mismatched cases and writes `server/eval/results.json`. The workflow does **not** run this command as a separate job. It also does not enforce the score as an automated threshold; review the output. The documented target is at least 30/40.

For live LLM evaluation, configure an authorized provider and run:

```sh
make eval-live
```

This makes live provider calls and may incur cost. It is not part of CI.

For live STT, first start the server with `DEMO_MODE=false`, `DEMO_CONTROLS_ENABLED=true`, the migrated isolated app database, and valid `STT_*` settings. Then run the smoke with one or more real audio files:

```sh
cd server
../.venv/bin/python -m e2e.smoke \
  --base-url http://127.0.0.1:8000 \
  --voice /path/to/clip1.m4a \
  --voice /path/to/clip2.wav
```

The smoke script checks that each upload returns a successful message status and prints its transcript; it does not score transcript accuracy or verify the clip's expected parsed fields. Review those manually against known expected meaning. Use synthetic content and the isolated app database.

## Expected warnings and reporting

- The suite may print existing Starlette/httpx or SQLite `ResourceWarning` warnings while still passing. Record warnings separately from test failures.
- Report the actual exit status, test count, Python/PostgreSQL versions, migrations, seed reruns, smoke result, and any failing case. Never label a skipped live provider/audio check as passed.
- To inspect a CI failure, compare the failed job/step with this runbook. The CI workflow uses Python 3.12 and PostgreSQL 16; a local run on other versions is useful but not an exact environment match.
