# Full-system E2E test steps

Use this guide to validate OJA against the acceptance criteria in [final-prd.md](../../final-prd.md), including the real PostgreSQL database, LLM, speech-to-text service, and (when integrated) the Flutter client.

## Current CI coverage and client status

The current [backend-tests.yml](../../.github/workflows/backend-tests.yml):

- Runs on matching pushes to `oja`, pull requests targeting `oja` or `main`, and manual `workflow_dispatch`.
- `tests` job runs the complete `unittest` suite on SQLite, with fake providers.
- `postgres` job starts PostgreSQL 16; upgrades migrations, checks for schema drift, downgrades all the way to base and reapplies migrations, runs the reference seed twice, runs the complete test suite with `TEST_DATABASE_URL` set to a separate throwaway database, and runs `server/e2e/smoke.py` against a live Uvicorn server in `DEMO_MODE`.
- Neither CI job calls the live LLM or STT provider. The automated HTTP smoke checks the offline demo flow; it does not upload voice clips unless `--voice` is explicitly supplied.
- CI does not run `make eval-live`, Flutter checks, or Android device E2E. The repository does not show whether branch protection requires these workflow jobs to pass before merge.

Thus PostgreSQL migrations, idempotent reference seeding, the PostgreSQL-backed automated tests, and the offline real-HTTP/WebSocket golden-path smoke are already CI-automated. The extended scenarios below are for PRD acceptance cases not asserted in that smoke, real-provider checks, or any step marked as a client/device test.

The Flutter client is **not yet integrated with this backend**. Its [API client](../../client/lib/core/api/oja_api.dart) and [base URL](../../client/lib/core/api/config.dart) target the legacy `backend.py` API, not the `server/` API contract. Do not point the app at this backend and assume it is compatible. The backend's voice endpoint can be tested directly with real audio without the Flutter app; testing microphone permissions, recording UI, processing indicators, and the complete phone-to-server journey requires the client to be integrated first. The implementation plan also explicitly defers the dashboard UI.

## Test boundaries and prerequisites

Run live tests only in a local, non-production environment using synthetic trader/customer data.

Have these available:

- Python environment and packages from the repository `requirements.txt`.
- A running PostgreSQL instance and a **new, dedicated E2E database**. Do not use the configured/shared `oja` database: the test fixture drops and recreates tables.
- A reachable, configured OpenAI-compatible LLM endpoint for live extraction and intent tests.
- A reachable, configured OpenAI-compatible speech-to-text endpoint for real audio tests. For local whisper.cpp, follow the repository's setup guidance; M4A conversion requires `--convert` and ffmpeg.
- Five short, locally stored Pidgin/English audio recordings with known expected meaning, and permission from each speaker to record/use them.
- For phone testing: an Android phone (the PRD demo target) and laptop on the same network, with firewall access to the laptop's API port.

Keep `.env`, API keys, session tokens, claim secrets, and test audio containing personal information out of Git, screenshots, terminal transcripts, and the final report. Do not enable demo controls in a shared or deployed environment.

## 1. Prepare an isolated PostgreSQL environment

1. Create two new, empty databases owned by the role in your local `.env`, for example `oja_e2e_app_YYYYMMDD` and `oja_e2e_test_YYYYMMDD`. Do not drop/reuse an existing database.
2. In a terminal at the repository root, point migrations and the running server at the app database, and point the test fixture at the separate test database. Use local values; do not put credentials in the guide or commit them:

   ```sh
   export E2E_APP_DATABASE_URL='postgresql+psycopg://<role>:<password>@127.0.0.1:5432/<app-database>'
   export E2E_TEST_DATABASE_URL='postgresql+psycopg://<role>:<password>@127.0.0.1:5432/<test-database>'
   export DATABASE_URL="$E2E_APP_DATABASE_URL"
   export TEST_DATABASE_URL="$E2E_TEST_DATABASE_URL"
   ```

   Do not point both variables at the same database. The test fixture drops/recreates its mapped tables. This is also how CI separates its migrated application DB from its test DB.

3. Set the runtime mode for **live** provider checks:

   ```sh
   export DEMO_MODE=false
   export DEMO_CONTROLS_ENABLED=true
   ```

   `DEMO_CONTROLS_ENABLED=true` is only for this isolated local E2E environment, so the demo trader can be seeded. `DEMO_MODE=false` is necessary to exercise the configured LLM. Provider configuration (`LLM_*`, `STT_*`) is read from the root `.env` or the process environment.

4. Apply and validate migrations:

   ```sh
   .venv/bin/alembic upgrade head
   .venv/bin/alembic check
   ```

   **Pass:** migrations reach head and `alembic check` reports `No new upgrade operations detected.`

## 2. Run the complete automated backend suite on PostgreSQL

This suite is already run in CI. To reproduce it locally, run serially with the isolated app and test database variables above:

```sh
cd server
../.venv/bin/python -m unittest discover -s tests -t . -v
```

**Pass:** all discovered tests pass. Save the test count, elapsed time, failures/errors, Python version, and PostgreSQL version in the run record.

The suite intentionally replaces providers with fakes and does not make live LLM/STT calls. `TEST_DATABASE_URL` causes the test fixture to drop/recreate mapped tables for each test, so:

- Never run this command against a database containing useful data.
- Keep `TEST_DATABASE_URL` separate from the app/server `DATABASE_URL`.
- No migration restoration is needed on the app database: the tests use the separate test database. The test database is intentionally left without its mapped tables after the run.

## 3. Start the backend and run the automated black-box smoke

This migrated-PostgreSQL HTTP/WebSocket check is already run in the CI `postgres` job in `DEMO_MODE`. To reproduce it locally, first migrate and seed the app database (not the test database):

```sh
.venv/bin/alembic upgrade head
.venv/bin/alembic check
cd server
../.venv/bin/python -m app.demo.index
```

With `DATABASE_URL` pointing at the isolated app database, set `DEMO_MODE=true` and `DEMO_CONTROLS_ENABLED=true`, then start Uvicorn:

```sh
cd server
DEMO_MODE=true DEMO_CONTROLS_ENABLED=true ../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In a second terminal:

```sh
cd server
../.venv/bin/python -m e2e.smoke --base-url http://127.0.0.1:8000
```

The smoke resets and seeds demo data in the configured database. It checks `/health`, reset/seed, WebSocket ping and event delivery/closure, cash and credit sales, a nickname payment, clarification, stock/customer/Home figures, `/ask`, suggestions, consent approval/token claim/totals-only summary, logout and old-token rejection. Do not point it at shared or useful data. Use `/docs` and [FRONTEND_HANDOFF.md](../../FRONTEND_HANDOFF.md) for current API shapes.

For a physical phone, use the laptop's reachable LAN IP rather than `127.0.0.1`; both devices must be on the same network. Do not expose this test server to the public internet.

## 4. Run backend black-box API flows

Use `/docs` or an HTTP client to make these requests. Use unique phone numbers and `client_message_id` values for every run; reuse the same message ID only when intentionally testing a retry. Capture status, response, and the corresponding API readback without recording bearer tokens.

### 4.1 Onboarding, profile, authentication, and isolation — FR-S21/S22

1. Create a synthetic trader with a unique phone, a seeded location, a PIN, and at least one item with an opening quantity.
2. Confirm onboarding succeeds and returns a session token. Read the profile and inventory using that token.
3. Confirm the item and opening stock appear. Update profile fields and verify they persist on the next GET.
4. Try an unknown location, a duplicate phone, and a missing required field; confirm validation/error responses do not create a second/partial trader.
5. Log out or use an invalid token and confirm protected endpoints reject it. Create a second trader and confirm the first trader's token cannot read or modify the second trader's profile or inventory.
6. If testing PIN lockout/expiry, use only this dedicated database and temporary test settings; confirm login behavior and session rejection, then restore normal settings.

### 4.2 Text capture, clarification, correction, and idempotency — FR-S1/S3-S8, NFR-3/NFR-5

1. Submit a clear sale, credit sale, payment, and expense with distinct message IDs. Check the saved entry, confirmation text, customer and item associations, and raw text through the API.
2. Submit an ambiguous message such as `I sell two bags and half`. Confirm the API asks one amount question and does not create a saved entry yet; reply `25k` using a new ID and verify one saved entry with the expected amount and quantity.
3. Correct a saved entry with `No, I mean four bags`. Confirm the entry ID remains the same, the new value is shown, and the edit/audit behavior matches the API.
4. Send a gibberish/off-topic message; confirm a polite fallback and no new saved entry.
5. Replay the exact request with its original `client_message_id`; confirm the original response is replayed and no duplicate entry or stock movement is created.
6. For a controlled provider-failure check, make the configured LLM endpoint unavailable only in this isolated environment. Submit a new message; confirm a clear error and no partial ledger write. Restore the provider and verify a retry with the same ID can succeed.

### 4.3 Real transcription and voice-to-ledger — FR-S2, FR-C1/C2, NFR-2/NFR-3

This backend test does **not** require the Flutter client. The smoke script accepts repeatable `--voice` arguments and sends actual recordings to `POST /messages` as multipart form data. The CI job does not supply clips, so real transcription is not part of its routine pass. To try a local clip with a server configured for a reachable STT provider:

```sh
cd server
../.venv/bin/python -m e2e.smoke --base-url http://127.0.0.1:8000 --voice /path/to/clip.m4a
```

Repeat `--voice` for more clips. The script prints the returned transcript and checks that each upload returns a `saved`, `clarify` or `fallback` response; it does **not** judge transcript accuracy or assert all parsed fields against an expected transcript. Complete the manual review below for each clip:

1. Confirm the configured `STT_BASE_URL`, inference path, model, credentials (if required), timeout, and accepted audio format work from the backend host.
2. Prepare five short Pidgin/English recordings. Include a clear sale with an amount, a credit sale with a customer, a payment using a known nickname, a phrase with a due date, and one noisy or ambiguous clip. Record the expected words/meaning separately; use synthetic names and amounts.
3. For each clip, submit `audio` and a unique `client_message_id` with a valid trader bearer token. Use the actual content type (`audio/m4a`, `audio/wav`, etc.). Do not send clips to the legacy `/transcribe` route.
4. For each response, verify:
   - The request succeeds or produces an explicit transcription/provider error.
   - The transcript is returned and stored as the entry's `raw_text`.
   - The parsed type, item, quantity, amount, customer, and due date are correct, or a clarification is requested instead of a fabricated entry.
   - The entry, stock, customer balance, and Home totals agree with the resulting database/API readbacks.
5. Upload one unsupported content type and one file larger than `STT_MAX_UPLOAD_MB`; confirm the API rejects them without a saved entry.
6. In the isolated environment only, stop/unconfigure the STT service and upload a valid clip. Confirm an explicit error and no partial write. Restore STT and retry with the same ID.

**Record for each clip:** filename (not personal data), language/accent notes, expected transcript/meaning, returned transcript, outcome, duration, and pass/fail. The PRD does not define a numeric word-error-rate threshold; do not invent one. Report every mismatch for product/QA review.

### 4.4 Live LLM extraction and evaluation — FR-S3/S9/S11/S18-S20, NFR-1/NFR-8

1. Confirm `DEMO_MODE=false` and the configured LLM endpoint/model are reachable. Never print or commit the API key.
2. Run the offline evaluation for a reproducible baseline:

   ```sh
   make eval
   ```

3. After checking that live calls are authorized and within the provider budget, run:

   ```sh
   make eval-live
   ```

4. Record the live score, per-case failures and hard-case score from the command output/results artifact. The documented target is at least 30/40; the cases still require an independent reviewer. A passing score does not replace the voice or phone journey.
5. Confirm model-generated answers cannot change amounts, balances, stock, Home totals, or suggestion rankings. Compare those values with the database-backed endpoints.
6. Rate-limit retry behavior is already covered with a mocked provider in automated tests. Only exercise a real provider's rate-limit path when the provider supports a safe test/quota; do not deliberately exhaust a production quota.

`make eval-live` invokes the configured live LLM and can incur cost. The eval harness uses an in-memory database; it is not a live HTTP-server test.

### 4.5 Inventory, Home, questions, suppliers, and consent — FR-S9-S17, S23-S32

1. Add an inventory item and record opening stock, a restock, and an adjustment. Verify quantity on hand is derived from the movements; editing item details must not edit quantity.
2. Save a sale against a stocked item, then correct it. Confirm stock changes once and the correction updates the same movement. Test oversell and an untracked item; verify the documented warnings.
3. Create a credit sale and payment for a known customer. Verify balance is derived correctly, aliases resolve, overdue status uses the due date, and one trader cannot see another trader's customer.
4. Ask `Who owes me?`, a stock-level question, today's total, and a restock question. Compare every figure/order against `/customers`, `/inventory`, `/home`, and `/suggestions`.
5. Verify Home periods (today, 7d, 30d), expenses/profit, recent entries, low-stock card and top suggestion. Check suggestion offers are labelled demo data and match `/suggestions`.
6. Create an access request for a synthetic registered trader. Approve it as that trader, claim the agent token once, and read only the allowed summary scopes.
7. Verify rejection, missing/invalid/expired/revoked token behavior, immediate revocation, and access-log rows. Confirm the summary omits customer names, raw text, entry IDs, phone and location. Do not put tokens in test evidence.

### 4.6 WebSocket and resilience — FR-C13, NFR-3/NFR-4

1. Connect to `/ws?token=<trader-session-token>` and submit a new message. Confirm the expected event is delivered after the write is committed.
2. Confirm another trader does not receive that event. Log out or expire the session and confirm the socket closes with the documented authentication close code.
3. With providers unreachable, confirm the application displays explicit failure behavior and no half-saved entry. Separately set `DEMO_MODE=true` on the isolated environment and rerun the offline golden path; confirm it makes no provider calls.
4. Do not test demo reset against shared or useful data: `POST /demo/reset` deletes trader data.

## 5. Full Flutter-on-device E2E — blocked until API integration

The following PRD acceptance criteria require the Flutter app to call this backend and cannot currently be signed off using the existing client:

1. Integrate the app with the `server/` API contract, replace the legacy route shapes, and configure the API base URL for the local network. Do not use the current default Render URL as evidence against this backend.
2. Run onboarding on an Android phone: enter trader details, location and items, submit, land on Home, force-close/reopen, and confirm the authenticated session is retained.
3. Type a message and record each of the five audio clips from the phone. Confirm microphone permission, processing indicator, clear failure states, transcript/raw text, saved entry and updated figures.
4. Confirm a clarification displays in chat and the next user message completes it. Correct an entry and verify the same entry is updated. Retry after a simulated network interruption and confirm no duplicate.
5. Navigate Home, Assistant, Inventory and Profile. Verify Home refreshes after an entry; period totals and inventory updates match API responses; profile edits persist; all four screens are reachable.
6. Request lender access while the trader app is open. Confirm the consent prompt appears within five seconds; test Approve, Reject, and Revoke. Confirm the agent receives only approved totals and sees an error after revocation.
7. Measure the PRD thresholds on the same local network: text under 5 seconds, voice under 10 seconds, Home update within 3 seconds, and suggestions under 5 seconds. Record device, network, sample count and timing; report outliers rather than averaging them away.
8. Repeat on the intended release build from the candidate tagged commit. Use an emulator only as a documented fallback; the PRD targets a physical Android phone.

Do not mark these as passed until the client uses the new backend. Current client widget/unit tests exercise local client logic and do not verify backend requests.

## 6. Known gaps and report format

- **NFR-10 structured message logs:** implementation plan lists this as open. Verify and record as **not implemented/not passable yet** unless the implementation changes; do not infer successful observability from a successful API response.
- **FR-S19 eval review / live score:** cases still need an independent review. `test_eval_cases` runs all 40 through the offline runner but does not assert a score threshold; run `make eval` to see the score and mismatches. The last observed offline score is 37/40 (7/10 hard). CI does not run the live LLM evaluation, and the live score has not been measured.
- **Voice accuracy:** five real clips remain to be tried with the selected STT provider.
- **Client E2E:** blocked until the Flutter app is integrated with the new server API.
- **CI:** PostgreSQL migrations/schema check, idempotent reference seeding, PostgreSQL-backed tests and the offline HTTP/WebSocket smoke are automated. Live LLM/STT, clip accuracy review, Flutter/device E2E, and Flutter checks are not.
- **Dashboard UI:** not implemented in the current scope/decision; exercise consent and agent flows through their API endpoints unless the product scope changes.

For each run, record date/time, branch/commit, environment (local/CI/device), Python/PostgreSQL/provider versions, database name (never credentials), test step, exact request scenario (never tokens), expected result, actual result, duration, pass/fail/blocked, and a sanitized error/reproduction procedure. Mark unrun and blocked items explicitly; do not report a skipped or provider-faked test as a live integration pass.
