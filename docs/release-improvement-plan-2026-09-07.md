# ECDAT release improvement implementation plan

Date: 2026-09-07

Status: implemented and verified on `fix/sha1-recommendation`.

## Objective

Turn the current verified feature set into a coherent release candidate: repair
deployment and output-integrity defects, make repository scans relevant and honest
at scale, harden the dashboard's data/error states, rerun every release gate, then
commit and push the existing `fix/sha1-recommendation` branch.

## Stage 1 — Release blockers and API integrity

1. Package and run Alembic migrations through a one-shot Compose service before
   the backend starts.
2. Make `/ready` reject missing or outdated application schemas.
3. Reject report/CBOM/evidence/evaluation requests for incomplete scans and handle
   `scan_id=0` explicitly.
4. Constrain risk-context fields to the supported enums and bound audit/history
   pagination.
5. Remove duplicate migration constraints, dispose migration engines, and add
   regression coverage.
6. Bring the CBOM response into CycloneDX 1.6 shape while retaining ECDAT metadata
   through standard `properties`.

## Stage 2 — Scanner relevance and scale safety

1. Introduce a source-repository scan profile that excludes virtual environments;
   retain an explicit environment profile for `site-packages` discovery.
2. Surface unreadable-directory traversal failures so coverage cannot silently
   overstate scope.
3. Normalize failure paths consistently with the API contract.
4. Add bounded aggregate evidence handling and document remaining OS-level memory
   and CPU isolation limits.
5. Keep the consumed v3 benchmark qualification adjacent to every accuracy claim.

## Stage 3 — Frontend correctness and hardening

1. Preserve selected `scan_id` across Overview, Reports, CBOM, Inventory and all
   downloads; make “View CBOM” navigate instead of downloading unexpectedly.
2. Replace swallowed request failures with explicit retryable error states.
3. Bound large Scan Detail/Reports/CBOM rendering and index graph edges once.
4. Add reliable asset-save status with retry/recovery semantics.
5. Remove remote Google Font requests, fix verified contrast failures, and enforce
   44px touch targets on primary interactive controls.
6. Add focused unit/E2E coverage one behavior at a time before implementation.

## Stage 4 — Release gate and publication

1. Backend, migration, scanner, benchmark, frontend unit, Edge E2E, formatting,
   TypeScript and production-build checks.
2. Bandit, pip-audit, npm audit, tracked-secret and tracked-large-file checks.
3. Fresh disposable Docker/PostgreSQL verification from an empty volume, including
   migrations, schema-aware readiness, scan, outputs and restart persistence.
4. Impeccable detector plus one desktop/mobile visual confirmation pass.
5. Review the complete diff, commit the intentional existing work and audit fixes,
   then push `fix/sha1-recommendation` to `origin`.

## Deferred production work

SSO, password hashing or an external identity provider, distributed scan admission,
durable queues, OS sandboxing, hard memory/CPU quotas, streaming multi-million-row
exports, backup/restore, TLS termination and high availability remain separate
production projects. They must not be implied by this release gate.
