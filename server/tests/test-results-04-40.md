# Backend test results — 2026-10-24 04:40 (+01:00)

## Summary

**PostgreSQL integration tests: PASS (135/135).**  
**Black-box HTTP workflow against PostgreSQL: PASS.**  
**Alembic migrations and schema check: PASS.**  
**Failures found: none.**

No application code or test code was changed. The standalone unit-test modules were not rerun, per request.

## What exists in the project

There is no separately named `integration/` test directory, but the API and workflow tests under `server/tests/` are integration-style: they run the real FastAPI app through `TestClient` and a SQLAlchemy database. `tests/support.py` defaults to in-memory SQLite and supports PostgreSQL through `TEST_DATABASE_URL`; it drops and recreates the mapped tables for each test. Provider calls are replaced with deterministic fake LLM and speech-to-text implementations. The test suite therefore covers app/API/database behavior, but not a real LLM or transcription service.

To avoid the configured application database (`oja`), a separate database named `oja_integration_test_20261024` was created in the already-running local PostgreSQL container and used for this run. The configured application database was not targeted. The dedicated test database is left in place with test/demo data; no cleanup or destructive database operation was performed.

## Tests run

### PostgreSQL-backed API/workflow suite

Ran these modules from `server/` with `TEST_DATABASE_URL` pointed to the isolated database:

- `tests.test_ask_api`
- `tests.test_auth_api`
- `tests.test_consent_api`
- `tests.test_customer_resolution_api`
- `tests.test_demo_mode`
- `tests.test_home_customers_inventory_api`
- `tests.test_inventory_api`
- `tests.test_ledger_workflows`
- `tests.test_messages_api`
- `tests.test_onboarding_profile_api`
- `tests.test_realtime_api`
- `tests.test_suggestions_api`

**Result:** 135 tests passed in 32.133 seconds; 0 failures and 0 errors. This includes the automated eight-step offline golden path. An existing `StarletteDeprecationWarning` notes that using `httpx` with `starlette.testclient` is deprecated; it did not fail the run.

### PostgreSQL migrations

On the isolated database:

- `alembic upgrade head` — passed; applied `645c930b9cc6`, `c3819b46ad50`, `5b14d59c5953`, and `355529bd3baa`.
- `alembic check` — passed: `No new upgrade operations detected.`

### Manual black-box HTTP workflow

Started Uvicorn on localhost with `DEMO_MODE=true` and `DEMO_CONTROLS_ENABLED=true`, using the isolated PostgreSQL database. Seeded reference data and exercised the real HTTP server. All checks passed:

1. `GET /health`.
2. `POST /onboarding`, including an opening inventory item.
3. `POST /demo/seed` and authenticated trader requests.
4. `POST /messages`: a credit sale to Mama Ngozi for ₦60,000.
5. Clarification for “I sell two bags and half,” followed by “25k.”
6. Correction “No, I mean four bags,” confirming the same ledger entry was updated.
7. “The rice woman don pay thirty k,” resolving the nickname to Mama Ngozi.
8. `POST /ask` for “Who owes me?” and `GET /home?period=7d`, verifying derived balances/totals.
9. Consent request, trader approval, one-time claim and scoped `GET /agent/summary`.

The manual message workflow used text for the credit-sale step. It did **not** upload real voice audio or call an actual speech-to-text provider.

## Failures and reproduction

**No failures were found**, so there are no failure reproduction steps.

## Not tested or still open

These are coverage gaps or documented open work, not failures observed in this run:

- **Real voice/STT:** Test five recorded Pidgin clips against the selected speech-to-text provider; the manual HTTP check used text and the automated tests fake transcription. The implementation plan lists this as open.
- **Live LLM evaluation:** No live provider calls or `make eval-live` run. The implementation plan records the offline evaluation as 37/40 and says the cases still need a second reviewer; confirm the current score with a fresh evaluation before relying on it.
- **Flutter/device E2E:** The implementation plan says the Flutter client has not been integrated with this backend. On-device onboarding, microphone permissions/audio upload, UI rendering and retry behavior remain unverified.
- **Structured message logging:** One structured log line per message (NFR-10) is listed as open in the implementation plan.
- **Performance targets:** This run did not measure the PRD’s individual response-time targets.

The backend already has automated API/workflow integration tests, so new integration tests do not need to be written just to test the existing backend flows. The remaining manual work is mainly real-provider, real-audio and client/device validation.

## Reproduction notes

Use a **dedicated test database**, not the configured application database: the test fixture drops and recreates its mapped tables. For the PostgreSQL suite, run the listed `unittest` modules from `server/` with `TEST_DATABASE_URL` set to the dedicated database URL. For the migration check, point `DATABASE_URL` at that same isolated database and run `alembic upgrade head` followed by `alembic check`. For the black-box path, migrate and seed that database, set `DEMO_MODE=true` and `DEMO_CONTROLS_ENABLED=true`, start Uvicorn, then follow the HTTP sequence above.
