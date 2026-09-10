# ECDAT-SIH Improvement Plan

> Status update (2026-09-10): CI, coverage, lint, request tracing, rate limits, stale recovery, lockfile dependency parsing, resource budgets, database leases and authenticated progress events are implemented. Certificate enrichment, API v1 aliases, editable business context, a durable external queue and full reconnect semantics remain open.

```mermaid
flowchart LR
    P0[P0 foundations] --> P1[P1 operations]
    P1 --> P2[P2 discovery depth]
    P2 --> P3[P3 production scale]
```

**Date:** 2026-09-09
**Branch:** `fix/sha1-recommendation`
**Protected baseline:** `877f100d52e35f8af99450502425a7ba7689fe43`

---

## Context

ECDAT-SIH is a Smart India Hackathon 2026 project: a cryptographic asset discovery and risk assessment tool with a FastAPI backend, Python AST scanner, and React dashboard. The codebase is functional and tested (118 backend tests, 22 frontend tests, 7 E2E), but lacks production-grade observability, security controls, and operational resilience. This plan targets the verified gaps between the current state and the roadmap in `docs/improvements-plan-2026-09-09.md` and the work packages in `docs/IMPLEMENTATION.md`.

---

## Verified Current Architecture

From direct source inspection:

| Layer | Implementation | Key Files |
|---|---|---|
| Collection | Filesystem walk, excludes `.git`, `node_modules`, `dist`, `build`, `__pycache__` | `scanner/main.py:_inventory()` |
| Detection | AST collector, regex rule collector, dependency collector, cert collector | `scanner/collectors/ast_collector.py`, `rule_collector.py`, `dep_collector.py`, `cert_collector.py` |
| Normalization | `CryptoAsset` model with algorithm, category, evidence dict | `scanner/models/asset.py` |
| Correlation | Groups by (component, algorithm, usage, location, operation_anchor); detects conflicts | `backend/services/correlator.py` |
| Discovery Assurance | Multi-source confidence scoring (+0.08 per source, -0.20 conflict penalty) | `backend/services/confidence.py` |
| Risk | Mosca-style 0-100 score; quantum vulnerability, Mosca window, sensitivity, exposure | `backend/services/risk_engine.py` |
| Recommendation | Usage-aware PQC guidance (ML-KEM, ML-DSA, SLH-DSA) | `backend/services/risk_engine.py:_recommendation()` |
| Presentation | React 18 dashboard with Recharts, 6 pages, 4 shared components | `dashboard/src/pages/`, `dashboard/src/components/` |

**Auth:** HMAC-SHA256 signed demo tokens, 4 roles (admin, security_analyst, auditor, viewer), role-header fallback opt-in only (`ECDAT_ALLOW_ROLE_HEADER`).

**Scan Control:** Process-local `threading.Lock` with single `_active` flag; supervised subprocess with timeout (monotonic clock) and cancellation (threading.Event).

**Evidence Redaction:** `scanner.redaction.redact_evidence()` strips raw snippet/token/password fields.

**Persistence:** SQLAlchemy with PostgreSQL (prod) / SQLite (local); Alembic migrations; `pool_pre_ping=True`.

**CI:** `.github/workflows/ci.yml` already runs pytest, npm test, Playwright E2E with browser caching and failure artifacts.

---

## Existing Functionality to Preserve

| Feature | Implementation | Must Not Break |
|---|---|---|
| HMAC-signed session auth | `backend/security.py` — `issue_demo_token()`, `current_role()` | Login flow, role extraction, `ECDAT_ALLOW_ROLE_HEADER` opt-in |
| RBAC (4 roles) | `ensure_write_role()` restricts admin/security_analyst | Write endpoints, audit-logs access |
| Scan pipeline | `scanner_runner.py:_run_scan()` — scan→correlate→score→risk→persist | Pipeline order, metrics, failure handling |
| Evidence redaction | `scanner/redaction.py:redact_evidence()` | Token/password stripping in persisted evidence |
| Confidence scoring | `confidence.py:score_finding()` | Multi-source averaging, agreement bonus, conflict penalty |
| Risk model | `risk_engine.py:assess_risk()` | Mosca window, quantum vulnerability, explainable reasons |
| Scan cancellation/timeout | `scan_control.py:supervise()` with cancel Event and monotonic timeout | Worker process management |
| Audit logging | `security.py:record_audit()` | Append-only AuditLogDB |
| Repository guard | `repository_guard.py:resolve_repository()` — path validation, `ECDAT_ALLOWED_SCAN_ROOTS` | `/test-repo` special-case, allowed roots check |
| Scan limits | `scanner/limits.py` — file count, byte size, evidence count | Environment-variable-backed limits |
| Scan profiles | `source` and `environment` profiles controlling `.venv` inclusion | Profile switching via `ECDAT_SCAN_PROFILE` |
| Evaluation against ground truth | `backend/services/evaluation.py` + `test-repo/ground_truth.json` | Precision/recall/F1 calculation |
| Stale-job cleanup script | `scripts/cleanup_stale_scans.py` — standalone, dry-run, 3-hour threshold | Manual ops tooling |

---

## Problems with File-Level Evidence

### P0 — CI & Repository Consistency (partially done)

| # | Problem | File | Evidence |
|---|---|---|---|
| P0-1 | CI already uses pytest and npm test — this is done. | `.github/workflows/ci.yml` | Lines 18, 28: `pytest -q`, `npm test -- --reporter=dot` |
| P0-2 | Coverage reporting is absent. No `.coveragerc`, no `coverage` dependency, no coverage step in CI. | `.github/workflows/ci.yml` | No coverage step between line 29 (test) and line 30 (build) |
| P0-3 | No lint configuration files. No `ruff.toml`, `.eslintrc`, or ESLint in package.json scripts. | `backend/`, `dashboard/` | Glob confirms no lint config files exist |
| P0-4 | `.gitattributes` exists but minimal — only `*.py text eol=crlf`. Missing rules for other text files. | `.gitattributes` | Single line present |

### P1 — Security and Observability

| # | Problem | File | Evidence |
|---|---|---|---|
| P1-1 | No request ID middleware. No `X-Request-ID` header generation or propagation. | `backend/main.py` | Lines 50-84: No middleware defined; only CORS middleware |
| P1-2 | No structured logging. `print()` calls used in `main.py`, `scan_control.py`, `scanner_runner.py`, `scanner/main.py`. | `backend/main.py:44,46`, `backend/services/scan_control.py`, `backend/services/scanner_runner.py:83,96,179`, `scanner/main.py:34` | Multiple `print()` calls across 4 files |
| P1-3 | No endpoint-aware rate limiting. Login endpoint accepts unlimited requests. | `backend/routers/auth.py` | Lines 24-26: `login()` has no rate limiting |
| P1-4 | No scan submission rate limiting. Expensive scan operations can be spammed. | `backend/routers/scan.py` | Lines 20-54: `post_scan()` has no rate limiting |
| P1-5 | Process-local scan admission flag (`_active`) — server crash leaves job permanently "running". | `backend/services/scan_control.py:26-28` | `_lock = threading.Lock()`, `_active: Control | None = None` |
| P1-6 | Stale-job cleanup is standalone (`scripts/cleanup_stale_scans.py`), not integrated into app lifecycle. | `scripts/cleanup_stale_scans.py` vs `backend/main.py` | No import or call to cleanup in lifespan |
| P1-7 | Evidence redaction is shallow — only checks top-level field names and simple string patterns. No path redaction, no credential pattern coverage. | `scanner/redaction.py` | Lines 4-16: Only checks 6 field names and 3 simple patterns |

### P2 — Scanner Depth and Assurance

| # | Problem | File | Evidence |
|---|---|---|---|
| P2-1 | Dependency collector only handles `requirements.txt` and `pom.xml`. No `package-lock.json`, `Gemfile.lock`, `go.sum`, `Cargo.lock`. | `scanner/main.py:144-147` | Only `requirements.txt` and `pom.xml` dispatch |
| P2-2 | Certificate posture is minimal — only algorithm detection, no expiry, key size, signature algorithm, trust role. | `scanner/collectors/cert_collector.py` | Need to verify current fields |
| P2-3 | No performance budgets. No timing/memory/file-count limits beyond the evidence count cap. | `scanner/main.py` | No duration or memory tracking in metrics |
| P2-4 | Ground truth may not cover Java API patterns comprehensively. | `test-repo/ground_truth.json` | Need to inspect current coverage |
| P2-5 | Hardcoded business context in scanner_runner.py — all assets get "medium" for every context field. | `backend/services/scanner_runner.py:108-112` | All 9 context fields hardcoded |

### P3 — Scale and Product Workflows

| # | Problem | File | Evidence |
|---|---|---|---|
| P3-1 | No API versioning. All endpoints under `/api` with no version prefix. | `backend/routers/*.py` | All routers use `prefix="/api"` |
| P3-2 | No persistent queue. Scan control is process-local; crash loses admission state. | `backend/services/scan_control.py` | `_active` is a module-level variable |
| P3-3 | No progress events. Dashboard polls for scan status. | `dashboard/src/pages/ScanDetailPage.tsx` | Polling-based status updates |

---

## Prioritized Improvements

### P0 — Coverage and Lint Gates (stability)

**P0-A: Add coverage and lint to CI**
- Add `.coveragerc`, `ruff.toml`, `eslint.config.js`.
- Update `.github/workflows/ci.yml` with coverage, ruff, and ESLint steps.
- Add `npm run lint` to `dashboard/package.json`.
- Document in `README.md`.

**Files:**
- `.coveragerc` (new)
- `ruff.toml` (new)
- `eslint.config.js` (new)
- `.github/workflows/ci.yml` (edit)
- `dashboard/package.json` (edit)
- `README.md` (edit)

**P0-B: Complete `.gitattributes`**
- Add text-file EOL rules for markdown, TypeScript, JSON, YAML, shell scripts.
- Ensure `git diff --check` passes on Windows and Linux.

**Files:**
- `.gitattributes` (edit)

### P1 — Security and Operational Visibility

**P1-A: Request IDs and structured logging**
- Create `backend/logging_config.py` with JSON formatter.
- Add request-ID middleware to `backend/main.py`.
- Replace `print()` in `main.py`, `scanner_runner.py`, `scan_control.py`, `scanner/main.py`.
- Redact tokens, credentials, absolute paths in logs.

**Files:**
- `backend/logging_config.py` (new)
- `backend/main.py` (edit)
- `backend/services/scanner_runner.py` (edit)
- `backend/services/scan_control.py` (edit)
- `scanner/main.py` (edit)

**P1-B: Endpoint-aware rate limiting**
- Create `backend/middleware/rate_limit.py` — sliding-window rate limiter.
- Apply to `/api/auth/login` and `/api/scan`.
- Exempt `/health` and `/ready`.
- Return 429 with `Retry-After` and `X-Request-ID`.

**Files:**
- `backend/middleware/rate_limit.py` (new)
- `backend/main.py` (edit)
- `tests/test_rate_limiting.py` (new)

**P1-C: Interrupted-scan recovery integration**
- Extract stale-job logic to `backend/services/stale_job_recovery.py`.
- Call from `backend/main.py` lifespan (dry-run by default).
- Keep `scripts/cleanup_stale_scans.py` as thin CLI wrapper.
- Emit audit events for recovered jobs.

**Files:**
- `backend/services/stale_job_recovery.py` (new)
- `scripts/cleanup_stale_scans.py` (edit)
- `backend/main.py` (edit)
- `backend/services/scan_control.py:_finish_if_active()` (edit — add audit)
- `tests/test_cleanup_stale_scans.py` (edit)

### P2 — Scanner Depth and Assurance

**P2-A: Dependency collector expansion**
- Add `package-lock.json`, `Gemfile.lock`, `go.sum`, `Cargo.lock` to `dep_collector.py`.
- Dispatch from `scanner/main.py`.

**Files:**
- `scanner/collectors/dep_collector.py` (edit)
- `scanner/main.py` (edit)

**P2-B: Certificate posture enrichment**
- Add expiry, key size, signature algorithm, trust role to cert collector.

**Files:**
- `scanner/collectors/cert_collector.py` (edit)
- `tests/test_cert_collector.py` (edit)

**P2-C: Ground truth expansion and performance budgets**
- Expand `test-repo/ground_truth.json` with Java, alias, cert, TLS, dep fixtures.
- Add property-based tests.
- Add memory/time budgets to `scanner/limits.py`.

**Files:**
- `test-repo/ground_truth.json` (edit)
- `scanner/limits.py` (edit)
- `tests/test_precision.py` (edit)
- `tests/test_discovery_regressions.py` (edit)

### P3 — Scale and Product Workflows

**P3-A: Persistent scan queue with worker leases**
- Add lease table via Alembic migration.
- Replace `_active` flag with DB-backed claim.
- Reconcile expired leases on startup.

**Files:**
- `alembic/versions/` (new migration)
- `backend/models/scan_job.py` or new model (edit)
- `backend/services/scan_control.py` (edit)
- `backend/main.py` (edit)
- `tests/test_scan_safety.py` (edit)

**P3-B: Server-sent events for scan progress**
- Add `GET /api/scans/{id}/events` SSE endpoint.
- Update `scanner_runner.py` to emit progress events.
- Update dashboard `ScanDetailPage.tsx` and `client.ts`.

**Files:**
- `backend/routers/scan.py` (edit)
- `backend/services/scanner_runner.py` (edit)
- `dashboard/src/api/client.ts` (edit)
- `dashboard/src/pages/ScanDetailPage.tsx` (edit)

---

## Dependencies Between Improvements

```
P0-A (coverage + lint gates)
  └─ All other work (enforced gate)

P0-B (gitattributes)
  └─ P0-A (commits must be clean)

P1-A (request IDs + logging)
  └─ P1-B (rate limiter uses request IDs)
  └─ P1-C (audit events include request IDs)
  └─ P3-B (SSE uses request IDs)

P1-B (rate limiting)
  └─ P3-A (persistent queue needs rate limiting)

P1-C (stale-scan recovery)
  └─ P3-A (lease model reuses recovery logic)

P2-A (dep expansion)
  └─ P2-C (ground truth needs dep cases)

P2-B (cert enrichment)
  └─ P2-C (ground truth needs cert cases)

P3-A (persistent queue)
  └─ P1-C (recovery logic reuse)
  └─ P3-B (SSE needs DB-backed progress)
```

**Critical path:** P0-A → P1-A → P1-B → P3-A → P3-B
**Parallel track:** P0-B, P2-A, P2-B, P2-C (can proceed after P0-A)

---

## Risks and Rollback Considerations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Structured logging changes log format, breaking log parsing | Medium | Low | Additive only — old `print()` removed after logger confirmed |
| Rate limiting blocks legitimate bulk scans | Medium | Medium | Configurable via env vars; health/ready exempt |
| New lint rules cause CI failures | High (initial) | Low | Set permissive initial thresholds; tighten iteratively |
| Persistent queue migration requires DB schema change | Medium | High | Alembic migration; keep `_active` flag as fallback during transition |
| SSE endpoint requires frontend infrastructure changes | Medium | Medium | Implement as additive endpoint; polling remains functional |
| Certificate enrichment changes existing evidence shape | Low | Medium | Additive fields only; backward-compatible JSON |

**Rollback procedure:** Any change can be reverted with `git revert <sha>`. No destructive database migrations without Alembic downgrade path. Feature flags via environment variables for all new middleware.

---

## Acceptance Criteria

### P0-A: Coverage and Lint Gates
- CI runs with `pytest --cov=backend --cov-report=term-missing` and reports coverage.
- CI runs `ruff check backend/` and ESLint on `dashboard/src/`.
- Pull requests fail if coverage drops below measured baseline or lint violations exist.
- `npm run lint` and `npm run build` both succeed.

### P0-B: Gitattributes
- `git diff --check` reports zero whitespace errors on Windows and Linux.
- `git status --short` shows no spurious modified files after running checks.

### P1-A: Request IDs and Logging
- Every API response includes `X-Request-ID` header.
- Request ID appears in structured log entries and audit records.
- `print()` calls replaced in `main.py`, `scanner_runner.py`, `scan_control.py`.
- Sensitive values (tokens, passwords, absolute paths) never appear in serialized logs.
- `backend/logging_config.py` has JSON formatter with request ID support.

### P1-B: Rate Limiting
- `/api/auth/login` returns 429 after configurable threshold.
- `/api/scan` returns 429 after configurable threshold.
- `/health` and `/ready` return 200 during active throttling.
- 429 responses include `Retry-After` header and `X-Request-ID`.
- Configuration via environment variables documented.

### P1-C: Stale-Scan Recovery
- Recovery runs on app startup with dry-run default.
- Recovered jobs emit audit events.
- `scripts/cleanup_stale_scans.py` calls into the service module.
- Repeated cleanup is idempotent.
- Manual script produces identical results to in-app recovery.

### P2-A: Dependency Expansion
- `package-lock.json`, `Gemfile.lock`, `go.sum`, `Cargo.lock` produce evidence.
- Resolved versions appear in persisted asset records.
- Ground truth updated with lockfile cases; evaluation passes.

### P2-B: Certificate Enrichment
- Certificate evidence includes expiry dates, key size, signature algorithm.
- Trust role inferred (self-signed, CA-issued, etc.).
- Existing tests continue to pass.

### P2-C: Ground Truth and Performance
- Ground truth expanded with Java, alias, cert, TLS, dependency fixtures.
- Property-based tests pass for path handling and correlation identity.
- Scan completes within time budget on `test-repo`.

### P3-A: Persistent Queue
- Two API instances cannot claim the same scan job.
- Expired leases are recovered on startup.
- Existing scan lifecycle (cancel, timeout, completion) preserved.

### P3-B: SSE Progress
- `/api/scans/{id}/events` streams progress updates.
- Reconnection resumes from last persisted state.
- Dashboard shows live progress without manual refresh.

---

## Tests for Codex to Run After Implementation

```powershell
# 1. Backend unit tests with coverage
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider

# 2. Frontend tests
cd dashboard
npm test -- --reporter=dot

# 3. Frontend format check
npm run format:check

# 4. Frontend production build
npm run build

# 5. Lint checks
.\.venv\Scripts\python.exe -m ruff check backend/
cd dashboard && npm run lint

# 6. E2E tests
cd dashboard
npm run test:e2e

# 7. Full release gate (PowerShell)
.\scripts\verify_release.ps1

# 8. Verify no whitespace errors
git diff --check

# 9. Verify git status is clean
git status --short

# 10. Backend tests with coverage report
.\.venv\Scripts\python.exe -m pytest --cov=backend --cov-report=term-missing -q -p no:cacheprovider
```

**Target thresholds (initial):** Backend 80%, frontend 70% (to be raised from measured baselines).

---

## Proposed First Implementation Task

**P0-A: Add coverage reporting and lint gates to CI**

This is the recommended starting point because:
1. CI is already using pytest — adding coverage is a one-step extension.
2. The CI workflow file is the only file that needs editing for this task (plus new config files).
3. It establishes the gate that all subsequent work must pass through.
4. No application behavior changes; purely additive CI configuration.

**Files this task would modify (8 files, 3 new):**

| Action | File | Change |
|---|---|---|
| New | `.coveragerc` | Configure `[run] source=backend, omit=tests/*, branch=True` and `[report] fail_under=70` |
| New | `ruff.toml` | Target Python 3.11, line-length 100, select E/F/I/B (minimal rules) |
| New | `eslint.config.js` | TypeScript + React rules, no-config-returns, consistent with existing code |
| Edit | `.github/workflows/ci.yml` | Add `pip install pytest-cov`, coverage step, `ruff check` step, `npm run lint` step |
| Edit | `dashboard/package.json` | Add `"lint": "eslint src/"` script |
| Edit | `README.md` | Document `npm run lint`, coverage command, new CI steps |

**Assumptions/uncertainties:**
- ESLint may need `@typescript-eslint/parser` and `@typescript-eslint/eslint-plugin` — these may need to be added to `dashboard/package.json` devDependencies. Codex should verify current devDependencies first.
- The existing dashboard code may have lint violations that need addressing — the plan recommends a permissive initial config and tightening iteratively.
- `.coveragerc` format should be confirmed against the installed `coverage` package version in `backend/requirements-dev.txt`.
