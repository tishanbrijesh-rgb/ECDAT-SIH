# ECDAT project knowledge

Last verified: 2026-09-06  
Repository: `https://github.com/tishanbrijesh-rgb/ECDAT-SIH.git`  
Active branch: `fix/sha1-recommendation`

## Purpose

ECDAT is the SIH26164 privacy-first cryptographic discovery and assurance
prototype. It scans repositories without executing their code, correlates evidence
from independent collectors, measures confidence separately from coverage, and
produces explainable quantum-risk and migration guidance.

## Architecture

1. The React 18 dashboard authenticates users and calls the FastAPI API.
2. FastAPI validates roles, scan roots, limits and request data, then launches one
   isolated scanner child process.
3. Python AST, auditable multi-language rules, dependency manifests and X.509
   certificates produce normalized evidence.
4. Correlation groups evidence by file, operation, algorithm and usage while
   retaining disagreements.
5. Confidence, coverage, conflicts, blind spots and the Mosca-style risk model are
   calculated independently and persisted through SQLAlchemy.
6. PostgreSQL 16 is used by Docker Compose. SQLite remains available for local
   development and tests.
7. Inventory, CBOM, risk report, evidence graph, audit history and benchmark
   evaluation are exposed through authenticated API endpoints.

The highest-connectivity components in the current Graphify model are
`scan_with_metrics()`, `ScanJobDB`, `run_scan()`, `correlate()` and the scan-control
tests. Graphify reports no import cycles.

## Security and execution contract

- There are no default credentials. `ECDAT_USERS_JSON`, `ECDAT_TOKEN_SECRET` and
  `ECDAT_DB_PASSWORD` must be supplied outside Git.
- Data endpoints require signed sessions. Role-header impersonation is disabled by
  default.
- Scan roots, file size, file count and timeout are bounded. A process-level lock
  permits one active scan per backend process, and authorized users can cancel it.
- Linked files are not read. Oversized, malformed or failed supported files reduce
  measured coverage instead of being silently counted as processed.
- Scanner workers are separate child processes, but they are not a complete OS
  sandbox or memory boundary. Run one Uvicorn worker until admission and
  cancellation are coordinated outside the process.
- The dashboard production image is a multi-stage Node 22 build served by
  unprivileged nginx. Node, npm and development dependencies are absent at runtime.
- The backend image runs as UID/GID 10001 and does not contain compilers or build
  headers.

## Current verification evidence

The 2026-09-06 pre-migration release gate produced these results:

- 88 backend unit/API/regression tests passed; one Windows symlink test was skipped
  because symlink creation was unavailable.
- 7 frontend unit tests and 2 Microsoft Edge end-to-end tests passed.
- Python compilation, dependency consistency, Bandit medium/high analysis,
  TypeScript, Prettier and the Vite production build passed.
- `pip-audit` and `npm audit` reported no known application dependency
  vulnerabilities.
- No credential signatures or oversized tracked files were found.
- Docker and Compose configuration/build checks passed.
- The disposable Docker/PostgreSQL verifier passed three consecutive rounds after
  both production images were hardened. It checked readiness, authentication,
  scanning, CBOM/evaluation output, dashboard delivery, PostgreSQL connectivity and
  persistence after backend restarts, then removed its containers and volume.
- The dashboard runtime image is approximately 26 MB; the backend runtime image is
  approximately 77 MB.

## Accuracy evidence

- External benchmark v2: 45 operation labels, with the final scanner result repeated
  deterministically at 45 true positives, 0 false positives and 0 false negatives.
- Independently reviewed v3 holdout: 8 labels across seven complete Java files,
  repeated deterministically at 8 true positives, 0 false positives and 0 false
  negatives.
- These consumed, narrow corpora prove the recorded regressions. They do not prove
  general accuracy across every language, library or crypto category.
- The latest large local scan of `C:\Python314` processed 2,305 of 2,314 supported
  files (99.61%). Its nine failures were invalid parser fixtures and certificate/key
  fixtures, so this is a scale/coverage check rather than an accuracy claim.

## Important commands

```powershell
# Complete local code gate
.\scripts\verify_release.ps1

# Real disposable Docker/PostgreSQL test
.\.venv\Scripts\python.exe -m scripts.verify_compose

# Scanner CLI
.\.venv\Scripts\python.exe -m scanner.main test-repo

# External benchmark
.\.venv\Scripts\python.exe -m scripts.benchmark_external --manifest benchmarks\external-v3.json --repeat 3
```

## Current limitations and next work

- Phase 3 is pending explicit approval: introduce versioned database migrations and
  verify upgrade and rollback paths against PostgreSQL.
- Production SSO, TLS termination, secret management, backup/restore, distributed
  scan admission, hardened OS sandboxing and high availability remain future work.
- React 19, Recharts 3 and TypeScript 7 are optional major migrations, not current
  security fixes.
- Browser-download checks, presentation recording and offline screenshots remain
  presentation-machine tasks.

## Canonical references

- `README.md` — setup, product behavior and commands
- `docs/ARCHITECTURE.md` — system flow and assurance principles
- `docs/THREAT_MODEL.md` — trust boundaries and remaining threats
- `docs/five-step-verification.md` — detailed verification evidence
- `docs/authentication.md` — account and secret configuration
- `benchmarks/README.md` — external benchmark protocol
- `MEMORY.md` — concise handoff state for future work
