# Claude handoff prompt for ECDAT

Updated: 2026-09-10

Copy everything below into Claude while its working directory is the ECDAT
repository.

---

Continue development of ECDAT from the current repository state.

Repository context:

- Project: ECDAT — Enterprise Cryptographic Discovery & Analysis Tool
- Repository: `https://github.com/tishanbrijesh-rgb/ECDAT-SIH.git`
- Current branch: `fix/sha1-recommendation`
- Local repository: `C:\Users\Tishan Kumar B\Desktop\SIH\ECDAT-SIH`
- The working tree is intentionally dirty and contains important existing
  frontend improvements and completed Stage 1–4 work. Preserve all existing
  changes. Do not reset, discard, overwrite or broadly reformat them.

Before editing anything:

1. Read `MEMORY.md` completely.
2. Read `ecdat-sih-project-knowledge.md` completely.
3. Read `docs/verification-2026-09-10.md`.
4. Read `docs/IMPLEMENTATION.md`.
5. Run `git status --short`, `git diff --stat`, `git diff --check` and inspect the
   complete current diff.
6. Summarize what is already implemented, which changes belong to the user, and
   what work remains before making changes.

Current verified state:

- Stages 1–5 (Phase 3 migrations) are complete.
- Docker/PostgreSQL passed two disposable verifier invocations with 3/3 rounds
  each, including persistence across backend restarts and cleanup.
- Backend suite: 118 tests pass, 1 skip, and 84 subtests pass; migration tests restore
  `DATABASE_URL`, fixing the former cross-test scan-worker failure.
- Frontend: 22 unit tests pass; TypeScript, Prettier and Vite build pass.
- Chromium E2E: 7/7 workflows pass.
- Alembic migrations: 8/8 pass (upgrade, downgrade, data preservation, graph).
- `pip-audit` and `npm audit` report no known vulnerabilities.
- Bandit reports no medium/high findings.
- External v3 benchmark remains deterministic: 8 TP, 0 FP, 0 FN across three
  runs on its documented corpus.
- The `C:\Python314` scale scan inventoried 3,981 files, found 2,314 supported
  files, processed 2,303, reported 11 sanitized failures, and reached 99.52%
  supported-file coverage.
- Scan APIs expose failure records only as scan-root-relative paths plus fixed
  reason codes: `unreadable`, `oversized`, `linked_file`, `parse_error`, or
  `certificate_error`. Never expose absolute paths or raw exception messages.
- Certificate deprecation warnings and malformed metadata follow controlled
  failure paths while later valid PEM blocks continue.
- Scan Detail now loads assets through `/api/assets?scan_job_id=...` and renders
  sanitized failures.
- Scan failures persist via relational `scan_failures` table (Alembic migration
  0002). Legacy `__failed_file__:` prefixed entries in `blind_spots` are stripped
  by Pydantic validators for backward compatibility.
- Production uses migration-managed schema; `ECDAT_AUTO_CREATE_TABLES=false` in
  `docker-compose.yml`. Local/test mode allows implicit creation via env var.
- Migration 0004 adds database-backed scan leases. Structured request-ID logging,
  endpoint rate limits, stale recovery and authenticated SSE progress are present.

Critical constraints:

- Do not make major architectural changes, dependency major-version upgrades or
  unrelated redesigns without approval.
- Preserve the existing frontend design and behavior.
- Do not commit or push unless I explicitly request it.
- Do not add secrets, `.env` files, databases, virtual environments,
  `node_modules`, build output or `graphify-out` content to Git.
- Do not claim that testing proves the absence of all bugs. Report evidence,
  residual risks and test limitations honestly.
- Use focused tests before implementation for bug fixes, then run regression
  tests proportional to the risk.
- Save important findings, decisions and completed work in the appropriate Markdown
  files. Update `MEMORY.md` and `ecdat-sih-project-knowledge.md` before handing off.

Phase 3 and the scoped Phase 4 frontend/release hardening are complete. Remaining
work is production infrastructure hardening.

For your first response, do not edit code. Inspect the repository and provide:

- a concise verified status summary;
- any discrepancies between the documentation and current diff;
- discrepancies between the documented verification and the current branch;
- a prioritized plan for the next explicitly requested production milestone.

For future changes, work incrementally, preserve unrelated changes, and run these
verification commands as applicable:

```powershell
.\.venv\Scripts\python.exe -W error::ResourceWarning -m unittest discover -s tests
.\.venv\Scripts\python.exe -m scripts.benchmark_external --manifest benchmarks\external-v3.json --repeat 3
cd dashboard
npm test -- --run
npm run format:check
npm run build
$env:ECDAT_E2E_BROWSER_CHANNEL = "msedge"
npm run test:e2e
cd ..
.\.venv\Scripts\python.exe -m scripts.verify_compose
git diff --check
```

Docker Desktop is installed per-user. If `docker` is not on Claude's terminal
`PATH`, its CLI was available at:

`C:\Users\Tishan Kumar B\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe`

Begin by reading the required files and inspecting the repository. Do not start
a new production milestone until I approve your plan.

---
