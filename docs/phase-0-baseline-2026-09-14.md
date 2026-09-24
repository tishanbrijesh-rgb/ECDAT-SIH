# Phase 0 Baseline — 2026-09-14

## Outcome

The Phase 0 technical gate passes on the current working tree. No commits were
created and no pre-existing changes were reverted or regrouped. Release-state
cleanup remains a deliberate user decision because the tree contains 162
entries (100 modified and 62 untracked) spanning several workstreams.

## Repairs made while establishing the baseline

- Excluded `backend/tests` from production coverage measurement.
- Ignored rotated logs and generated accessibility reports.
- Repaired the ambiguous CBOM E2E selector.
- Replaced Playwright-owned Vite lifecycle management with a deterministic E2E
  runner that exits cleanly on Windows and remains usable in CI.
- Added `axe-core` as an explicit dashboard development dependency and made the
  Python accessibility runner resolve npm and Python executables portably.
- Added a login skip link/main landmark and removed prohibited ARIA from the
  empty toast container.
- Added focused accessibility and OpenSSL HMAC regressions.
- Detected the OpenSSL `HMAC(...)` API without reviving the existing Bouncy
  Castle `HMac(...)` false positive.
- Narrowed the visual-regression color-scheme type to Playwright's accepted
  literal values.

## Passing verification matrix

| Gate | Result |
|---|---|
| Backend tests | 353 passed, 4 skipped, 86 subtests passed |
| Backend branch coverage | 72.4% application-only; 70% gate passed |
| Ruff (enforced scope) | Passed |
| mypy (configured scope) | 47 files passed |
| Python dependency consistency | `pip check` passed |
| Alembic graph | Single `0006_provenance` head |
| Controlled scan and schema validation | Completed; 68 assets; schema passed |
| Corpus evaluation | Precision 85.71%, recall 96.00%, negative accuracy 100%; passed |
| Frontend formatting/lint/type/build | Passed |
| Frontend unit tests | 76 passed |
| Frontend browser tests | 52 passed; process exited cleanly |
| Public accessibility matrix | 4/4 passed; no serious/critical axe violations |
| npm dependency audit | 0 known vulnerabilities at install time |
| Whitespace check | Passed; line-ending conversion warnings only |

## Known limits and deferred risks

- Authenticated accessibility pages were not exercised because
  `ECDAT_A11Y_USERNAME` and `ECDAT_A11Y_PASSWORD` were not supplied. The public
  login matrix covered desktop/mobile and light/dark modes.
- Docker is unavailable on this host, so container/Compose execution remains
  unverified locally.
- The enforced Ruff scope passes, but a repository-wide scan also includes
  migration-format debt and intentionally vulnerable fixture repositories.
- Configured mypy does not type-check the backend package; this enforcement gap
  remains planned work.
- Corpus evaluation retains two false negatives where labels treat a digest
  parameter inside HMAC/ECDSA as a separate hash operation. The scanner's
  current evidence model intentionally avoids that double-counting.
- The E2E scan workflow still logs a mocked SSE 404 while passing. The audit
  plan requires unexpected console/network failures to become fatal before the
  internal demo gate.
- The current working tree is not release-ready until its 162 entries are
  reviewed and grouped. Runtime databases, logs, coverage, accessibility
  reports, screenshots, caches, and credentials must stay out of commits.

## Large-file scan

The largest current implementation hotspots (excluding corpora, generated
output, dependencies, and fixtures) are:

| File | Lines |
|---|---:|
| `dashboard/src/styles/pages.css` | 2,230 |
| `dashboard/src/styles/components.css` | 1,466 |
| `dashboard/src/styles/redesign.css` | 864 |
| `dashboard/src/pages/AssetsPage.tsx` | 798 |
| `dashboard/src/pages/Dashboard.tsx` | 749 |
| `backend/services/evaluation.py` | 707 |
| `dashboard/src/pages/CbomPage.tsx` | 615 |
| `scripts/a11y_check.py` | 578 |
| `dashboard/src/pages/ScanDetailPage.tsx` | 575 |
| `scanner/collectors/dep_collector.py` | 421 |
| `backend/main.py` | 340 |
| `backend/services/correlator_v3.py` | 385 |

These remain refactoring targets, not reasons to mix structural rewrites into
the trust/security fixes in Phase 1.

## Next gate

Phase 1 should begin with rate-limit correctness and trusted-proxy identity,
then readiness configuration validation, then scan-worker isolation. Every
behavioral fix must start with a failing focused regression and finish with the
full Phase 0 matrix.
