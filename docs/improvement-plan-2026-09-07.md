# ECDAT improvement plan — 2026-09-07

## Objective

Complete Docker/PostgreSQL verification, improve large-scan failure visibility,
harden certificate parsing, and expand browser coverage. Stop before Phase 3
database migrations until the user gives explicit approval.

## Working rules

- Preserve the current frontend work and dirty working tree.
- Use one red-green-refactor cycle per behavior change.
- Run focused tests after each change and the full release gate at each stage.
- Store only relative filenames and fixed reason codes; never expose exception
  messages, credentials or host paths.
- Do not add or change database columns before the Phase 3 migration framework.
- Do not commit Graphify output, build output, databases, secrets or `.env` files.

## Stage 1 — Docker/PostgreSQL verification

Status: complete. Two final verifier invocations passed 3/3 rounds each and
cleaned up all disposable resources.

Estimated time: 15–30 minutes after Docker is reachable; initial image downloads
may add time.

Steps:

1. Confirm `docker version` reports both client and server and
   `docker compose version` is available.
2. Run `docker compose config --quiet` with temporary verification credentials.
3. Run `.\.venv\Scripts\python.exe -m scripts.verify_compose`.
4. Confirm all three rounds pass readiness, authentication, scan completion,
   evaluation, CBOM output, dashboard delivery, PostgreSQL access and persistence
   after backend restart.
5. Confirm the randomly named verification project, containers and volume are
   removed by the verifier.

Completion gate: 3/3 rounds pass with no leftover `ecdat-verify-*` resources.

## Stage 2 — Sanitized failed-file reporting

Status: complete. The API/UI contract is implemented without a database schema
change, and focused plus full regression tests pass.

Estimated time: 1–2 hours.

Primary files:

- `scanner/main.py`
- `scanner/collectors/*.py`
- `backend/services/scanner_runner.py`
- `backend/schemas/asset.py`
- `dashboard/src/types.ts`
- `dashboard/src/pages/ScanDetailPage.tsx`
- `tests/test_scan_safety.py`
- `tests/test_ecdat.py`

Design:

- Track failures as a relative path plus a fixed code such as `unreadable`,
  `oversized`, `linked_file`, `parse_error` or `certificate_error`.
- Deduplicate failures when more than one collector examines the same file.
- Never return raw exception messages or absolute host paths.
- Before Phase 3, serialize concise sanitized entries through the existing
  scan-result JSON/blind-spot contract so no implicit database schema change is
  required.
- Show the failed count and an expandable failed-file list on Scan Detail with a
  clear empty state and accessible labels.

Tests:

- Oversized, unreadable, malformed and linked inputs receive the correct safe code.
- Absolute roots and exception text never appear in API responses.
- Duplicate collector failures produce one entry.
- Scan Detail renders failure entries and the zero-failure state.

Completion gate: focused scanner/API/UI tests pass, then the complete backend and
frontend gates pass.

## Stage 3 — Certificate parsing hardening

Status: complete. Deprecation warnings and metadata failures are contained,
mixed bundles continue, and the v3 benchmark remains unchanged.

Estimated time: 45–90 minutes.

Primary files:

- `scanner/collectors/cert_collector.py`
- certificate regression tests under `tests/`
- `docs/large-directory-scanning.md`

Design:

- Treat `CryptographyDeprecationWarning` for invalid certificate serial numbers as
  a controlled certificate failure instead of allowing future library versions to
  turn it into an unexpected crash.
- Continue scanning other PEM blocks/files when one certificate is invalid.
- Preserve valid certificate and public-key discovery behavior.
- Emit only the sanitized `certificate_error` reason through Stage 2 reporting.

Tests:

- A mocked non-positive-serial warning follows the controlled failure path.
- Malformed PEM, mixed valid/invalid bundles and valid certificates remain covered.
- The controlled repository evidence count and v3 benchmark stay unchanged.

Completion gate: no certificate deprecation warning escapes during regression
tests, and the full scanner/benchmark gate passes.

## Stage 4 — Browser E2E expansion

Status: complete. Seven full Edge workflows pass in three consecutive runs.

Estimated time: 2–4 hours.

Primary files:

- `dashboard/e2e/core-workflows.spec.ts` or focused files under `dashboard/e2e/`
- `dashboard/playwright.config.ts` only if additional projects are necessary
- existing Reports, CBOM and Scan Detail pages

Required scenarios:

1. Reports loads a selected scan and renders distribution and migration priorities.
2. CBOM switches among component, dependency-graph and raw JSON views.
3. Scan Detail renders metrics, assets, failure diagnostics and links.
4. CSV/report/CBOM downloads have the expected filename, MIME type and escaped data.
5. A 375-pixel viewport, dark mode, reduced motion, keyboard navigation and visible
   focus complete without horizontal overflow or inaccessible controls.

Completion gate: all Edge E2E scenarios pass alongside 11+ unit tests, TypeScript,
Prettier and the production build.

## Stage 5 — Phase 3 migration gate

Status: complete. All 8 Alembic migration tests pass. Three migrations
(0001_baseline, 0002_scan_failures, 0003_remove_implicit_creation) are
versioned and tested for upgrade, downgrade and data preservation.

Estimated time: 3–5 hours.

What was implemented:

- Alembic 1.19.2 configured with `env.py`, `alembic.ini`, and `ScriptDirectory`
  for programmatic migration control.
- Migration 0001: creates `scan_jobs`, `crypto_assets`, `audit_logs` tables
  matching current SQLAlchemy models exactly.
- Migration 0002: adds `scan_failures` table with `scan_job_id` FK, `path`,
  `reason`, `created_at`, indexes on `scan_job_id` and `(scan_job_id, path)`.
- Migration 0003: no-op recording migration-only schema management intent.
- `ECDAT_AUTO_CREATE_TABLES` env var guards `Base.metadata.create_all()` in
  production (`false` in docker-compose.yml, `true` by default locally).
- Scan failures persist via `ScanFailureDB` ORM rows in `scanner_runner.py`
  instead of JSON-encoded `blind_spots` strings.
- Pydantic `ScanJobResponse` coerces `ScanFailureDB` ORM objects via
  `ConfigDict(from_attributes=True)` and `field_validator(mode="before")`.
- Legacy `__failed_file__:` prefixed entries in `blind_spots` are stripped
  by schema validators for backward compatibility.

Completion gate: clean-database upgrade, populated-volume upgrade, application
smoke test and documented rollback/recovery all pass.

Next planned stage: Phase 4 (frontend enhancements, testing expansion, or
production hardening).

## Final verification after each implemented stage

```powershell
.\scripts\verify_release.ps1
.\.venv\Scripts\python.exe -m pytest -q
cd dashboard
npm test
npm run test:e2e
```

Docker stages additionally require:

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_compose
```
