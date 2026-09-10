# ECDAT verification report — 2026-09-07

> Historical snapshot. The current verification is [verification-2026-09-10.md](verification-2026-09-10.md).

## Verdict

The current frontend and backend code pass the local code, browser, security,
large-directory and Docker/PostgreSQL checks. Stages 1–5 are complete (including Phase 3 Alembic migrations). This is
not a complete production certification, and automated tests cannot prove that
no undiscovered bugs exist.

## Repository state

- Branch: `fix/sha1-recommendation`
- Release candidate: includes the user's frontend improvements and focused
  stabilization tests/fixes on `fix/sha1-recommendation`.
- Phase 3 database migrations: **complete** — 3 Alembic migrations, 8/8 migration
  tests pass.
- `git diff --check`: passed. Git reported informational LF-to-CRLF warnings for
  several dashboard CSS files.

## Code and behavior checks

| Area | Result | Evidence |
| --- | --- | --- |
| Backend tests | Pass | 117 tests pass; 1 skip; 84 subtests; migration environment isolation fixed the former flaky failure |
| Migration tests | Pass | 8/8 pass (upgrade, downgrade, data preservation, graph) |
| Frontend unit tests | Pass | 8 test files, 15 tests |
| Browser workflows | Pass | 7 Microsoft Edge E2E workflows passed in three consecutive runs |
| Python compilation | Pass | `backend`, `scanner`, `scripts`, and `tests` compiled |
| Python dependencies | Pass | `pip check` reported no broken requirements |
| Frontend types/build | Pass | TypeScript and Vite production build completed |
| Frontend formatting | Pass | Prettier reported all matched files formatted |
| External benchmark v3 | Pass | Three deterministic runs; 8 TP, 0 FP, 0 FN on the consumed seven-file Java corpus |

The frontend stabilization added regression coverage for loading-to-content
transitions on Dashboard, Risk Report and Scan Detail, plus the valid empty-CBOM
state. The dashboard API now refuses to present incomplete scans as completed
snapshots.

Scan Detail now retrieves its assets from the supported assets endpoint and
renders safe failed-file records. Reports, CBOM tabs, CSV download, mobile dark
mode, reduced motion and keyboard focus have browser coverage.

## Security checks

| Check | Result |
| --- | --- |
| `npm audit` | 0 known vulnerabilities |
| `pip-audit` | No known vulnerabilities |
| Bandit (`-ll`) | No medium/high findings |
| Tracked secret signatures | None found by the repository signature scan |
| Tracked files larger than 1 MiB | None found |

The first `npm audit` attempt inside the restricted sandbox could not reach the
registry or write its cache. It was rerun with approved advisory-service/cache
access and completed cleanly. The same applied to `pip-audit`; these were
environment failures, not discovered vulnerabilities.

## Large-directory scan

Target: `C:\Python314`

| Metric | Result |
| --- | ---: |
| Total files inventoried | 3,981 |
| Supported files | 2,314 |
| Successfully processed | 2,303 |
| Failed supported files | 11 |
| Supported-file coverage | 99.52% |
| Evidence records | 1,181 |
| Duration | 105,485 ms |

All eleven failures were returned as relative filenames with either
`certificate_error` or `parse_error`; no absolute root or parser message was
exposed. The stricter certificate policy explains the change from the earlier
baseline. Exact safe records are listed in
`stages-1-4-verification-2026-09-07.md`.

## Deployment verification

Docker Desktop 4.89.0, Engine 29.7.2 and Compose 5.5.0 were available. Two
complete disposable verifier invocations passed all three rounds. A final fresh
`ecdatverify` deployment also proved that the one-shot Alembic service completes
before the backend starts, readiness succeeds, login works, a real scan returns
61 assets at 100% supported-file coverage, and CycloneDX 1.6 output is served.
The checks include image builds, readiness, authentication, scanning, CBOM/evaluation output,
dashboard delivery, PostgreSQL connectivity, persistence after backend restarts
and cleanup. No `ecdat-verify-*` resources remained after verification.

## Recommended next work

1. Production SSO, TLS termination, secret management, backup/restore, distributed
   scan admission, hardened OS sandboxing and high availability remain future work.

Longer-term production work remains SSO, TLS termination, managed secrets,
backup/restore, durable/distributed scan admission, stronger OS sandboxing and
high availability.

## Commands used

```powershell
.\scripts\verify_release.ps1
.\.venv\Scripts\python.exe -m pytest -q
cd dashboard
npm test
npm run build
npm run format:check
npm run test:e2e
npm audit
cd ..
.\.venv\Scripts\pip-audit.exe -r backend\requirements.txt --progress-spinner off
.\.venv\Scripts\bandit.exe -q -r backend scanner scripts -ll
.\.venv\Scripts\python.exe -m scripts.benchmark_external --manifest benchmarks\external-v3.json --repeat 3
```
