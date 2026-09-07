# ECDAT stages 1–5 (including Phase 3) completion report — 2026-09-07

## Verdict

Stages 1–5 are implemented and verified. Phase 3 database migrations (Alembic,
versioned schema management, scan_failures table) are complete. The existing
frontend work was preserved.

## Implemented work

1. Docker Desktop 4.89.0, Engine 29.7.2 and Compose 5.5.0 were verified. The
   disposable PostgreSQL verifier passed two complete invocations, each with
   three persistence/restart rounds, and removed its containers, networks and
   volumes.
2. Scan list/detail responses now include `failures` records containing only a
   scan-root-relative path and one fixed reason: `unreadable`, `oversized`,
   `linked_file`, `parse_error` or `certificate_error`. Raw exceptions,
   absolute paths, traversal paths and internal persistence envelopes are not
   returned. The Scan Detail page renders the safe records.
3. Certificate deprecation warnings and lazy metadata failures now follow a
   controlled failure path. A bad PEM block does not stop later valid blocks.
4. Browser coverage now includes Reports, CBOM tabs, Scan Detail, sanitized
   failures, CSV downloads, a 375-pixel viewport, dark mode, reduced motion and
   keyboard skip-link focus.
5. A broken Scan Detail integration was also fixed: the client now combines the
   scan job with `/api/assets?scan_job_id=...` instead of relying on an ignored
   `include_assets` query parameter.

## Verification evidence

| Check | Final result |
| --- | --- |
| Docker/PostgreSQL | 2 verifier invocations; 3/3 rounds each; cleanup confirmed |
| Backend suite | 117 pass; 1 skip; 84 subtests; migration-environment flake fixed |
| Migration tests | 8/8 pass (upgrade, downgrade, data preservation, graph) |
| Frontend unit suite | 8 files, 15 tests passed |
| Edge E2E | 7/7 passed in three consecutive full runs |
| TypeScript/Vite | Production build passed |
| Formatting/diff | Prettier and `git diff --check` passed |
| Python dependencies | `pip check` passed |
| Vulnerability audits | `pip-audit` and `npm audit`: 0 known vulnerabilities |
| Static security | Bandit: no medium/high findings |
| External v3 benchmark | 3 deterministic runs; 8 TP, 0 FP, 0 FN |

The backend suite was also run by the focused implementation agents, and the
certificate and scan-failure tests were repeated independently.

## Large-directory scan

Target: `C:\Python314`

| Metric | Result |
| --- | ---: |
| Total files | 3,981 |
| Supported files | 2,314 |
| Processed files | 2,303 |
| Failed supported files | 11 |
| Coverage | 99.52% |
| Evidence records | 1,181 |
| Duration | 105,485 ms |

Sanitized failures:

- `Lib/site-packages/pip/_vendor/certifi/cacert.pem` — `certificate_error`
- `Lib/test/certdata/badcert.pem` — `certificate_error`
- `Lib/test/certdata/ffdh3072.pem` — `certificate_error`
- `Lib/test/certdata/nullbytecert.pem` — `certificate_error`
- `Lib/test/certdata/nullcert.pem` — `certificate_error`
- `Lib/test/certdata/pycakey.pem` — `certificate_error`
- `Lib/test/certdata/secp384r1.pem` — `certificate_error`
- `Lib/test/certdata/ssl_key.passwd.pem` — `certificate_error`
- `Lib/test/certdata/ssl_key.pem` — `certificate_error`
- `Lib/test/tokenizedata/bad_coding2.py` — `parse_error`
- `Lib/test/tokenizedata/badsyntax_3131.py` — `parse_error`

The stricter certificate policy intentionally records files containing rejected
or deprecated certificate blocks as failures, even when other blocks remain
usable. This explains the change from the earlier 9 failures/1,188 evidence
records to 11 failures/1,181 evidence records.

## Phase 3 completion summary

Phase 3 introduced versioned database migrations via Alembic 1.19.2:

- **Migration 0001_baseline**: Creates `scan_jobs`, `crypto_assets`, `audit_logs`
  tables matching current SQLAlchemy models exactly.
- **Migration 0002_scan_failures**: Adds `scan_failures` table with `scan_job_id`
  FK, `path`, `reason` (fixed codes), `created_at`, indexes on `scan_job_id` and
  `(scan_job_id, path)`.
- **Migration 0003_remove_implicit_creation**: No-op recording migration-only
  schema management intent.

Key files:
- `backend/models/scan_failure.py` — `ScanFailureDB` ORM model
- `backend/models/scan_job.py` — added `failures` relationship with cascade delete
- `backend/schemas/asset.py` — `ScanFailure` schema with `ConfigDict(from_attributes=True)`;
  `ScanJobResponse` validators coerce ORM objects and strip legacy `__failed_file__:` entries
- `backend/services/scanner_runner.py` — inserts `ScanFailureDB` rows directly
- `backend/main.py` — conditional `create_all` guarded by `ECDAT_AUTO_CREATE_TABLES`
- `docker-compose.yml` — `ECDAT_AUTO_CREATE_TABLES: "false"`
- `alembic/` — full Alembic setup (`env.py`, `alembic.ini`, 3 migrations)

## Remaining production work

- The scoped frontend correctness, accessibility and performance hardening in the
  release improvement plan is complete.
- Production SSO, TLS termination, secret management, backup/restore, distributed
  scan admission, hardened OS sandboxing and high availability remain future work.
