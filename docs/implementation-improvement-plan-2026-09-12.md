# ECDAT Improvement Plan — Post-Live-Scan

> Execution order: complete the [frontend improvement plan](./frontend-improvement-plan-2026-09-12.md) first, then continue with the backend, scanner, evaluation, and deployment work below.

## Verified baseline

- Live scan 8 completed successfully against `test-repo`.
- 9/9 in-scope files scanned, 0 failures, 100% operational coverage.
- 80 unique operation/capability records; average confidence 0.7775.
- Collector output: AST 18, rules 30, dependencies 30, certificates 2.
- Dashboard, inventory, risk report, CBOM, evidence graph, audit log, text report, and calibration endpoints return HTTP 200.
- Database integrity and foreign-key checks pass at Alembic revision `b2e4f1a7c39d`.
- External v3 benchmark is deterministic over three runs with 100% precision and recall.
- Broad controlled-dataset evaluation: precision 62.5%, recall 100%, F1 76.92%.
- Corpus gate: precision 85.71%, recall 96%, negative accuracy 100%.

## Phase 1 — Make deployment and readiness fail closed (P0)

1. Add a startup migration check that always validates the Alembic revision, including local development.
2. Remove or tightly constrain implicit `create_all`; it created an unversioned legacy database that returned HTTP 500 from every data endpoint.
3. Make `/ready` verify required columns, not only table names, when development auto-creation is enabled.
4. Add a migration bootstrap command that detects an existing unversioned legacy schema, validates it, stamps the matching revision, and upgrades without deleting data.
5. Add an integration test: legacy pre-phase-2 SQLite database → bootstrap → all primary endpoints return 200 and retain existing assets.

Acceptance: a stale or unversioned schema returns readiness 503 with an actionable message; the supported bootstrap path upgrades it without data loss.

## Phase 2 — Correct the evaluation model (P0)

1. Separate `observed_operation` metrics from `declared_capability` metrics. Dependency declarations should not count as operation-level false positives.
2. Expand the controlled ground truth beyond the current 15 component/algorithm pairs and label evidence kind, usage, location, and operation identity.
3. Report two scorecards:
   - operation precision/recall;
   - inventory/capability coverage.
4. Review the nine “unexpected” component/algorithm findings and classify each as true unlabeled evidence or detector false positive.
5. Gate CI independently on operation precision, operation recall, negative accuracy, and capability coverage.

Acceptance: evaluation no longer penalizes valid dependency capability evidence as an operation false positive, and every reported error maps to a reviewed label.

## Phase 3 — Raise detector precision without losing recall (P1)

1. Remove nested hash double-counting in HMAC APIs when the hash is only an algorithm parameter.
2. Add language-aware boundaries for SHA identifiers such as `SHA512_256`.
3. Add explicit OpenSSL `HMAC(...)` operation detection.
4. Review C/C#, Go, and JavaScript corpus false positives; add one regression fixture per corrected pattern.
5. Preserve the newly fixed Python comment masking and Java declaration filtering.

Target: corpus precision ≥95%, recall ≥95%, negative accuracy 100%, with external-v3 remaining 100% deterministic.

## Phase 4 — Improve confidence and risk usefulness (P1)

1. Replace synthetic calibration inputs with reviewed scan outcomes.
2. Calibrate separately by evidence kind and collector rather than using one global mapping.
3. Add confidence reliability diagrams and expected calibration error to the evaluation output.
4. Review why all 80 assets are only LOW or MEDIUM priority; ensure critical legacy algorithms can become HIGH/CRITICAL when business impact and exposure justify it.
5. Display capability-only findings separately from confirmed runtime use in the dashboard and risk report.

Acceptance: calibrated confidence is backed by reviewed labels, and risk tiers distinguish urgent observed use from low-confidence declared capability.

## Phase 5 — Complete runtime and UI resilience (P1)

1. Add a visible retry action and request ID to every frontend API error state.
2. Show a schema/migration-specific message when readiness is 503 instead of generic “unavailable.”
3. Add authenticated E2E coverage against the real backend and migrated SQLite/Postgres database, not only mocked routes.
4. Resolve the Windows Playwright shutdown leak so successful E2E runs exit with code 0 without manual process cleanup.
5. Add screenshots for empty, populated, loading, and failure states at desktop and 375px mobile widths.

Acceptance: all core user journeys work against a real migrated backend, error messages are actionable, and the E2E command terminates normally on Windows and CI.

## Phase 6 — Production verification (P2)

1. Run Compose with Postgres, migration, backend health check, and Nginx dashboard in a clean environment.
2. Verify restart persistence, migration idempotency, cancellation, concurrent scans, and stale-lease recovery.
3. Install and enforce Mypy in the development/CI toolchain.
4. Keep npm audit, pip-audit, Bandit, Ruff, unit tests, schema validation, corpus evaluation, and external benchmark as required CI gates.
5. Add backup/restore documentation before future schema changes.

Acceptance: a clean Compose deployment becomes healthy without manual database repair and survives restart with scan history intact.

## Recommended implementation order

1. Complete the frontend usability and design-system plan.
2. Deployment/readiness fail-closed checks.
3. Evaluation split and reviewed labels.
4. Precision regressions and calibration.
5. Real-backend E2E and Playwright shutdown.
6. Compose/Postgres and strict typing gates.
