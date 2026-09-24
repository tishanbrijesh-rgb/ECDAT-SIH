# ECDAT SIH Execution Plan

**Started:** September 22, 2026  
**Target:** Stable SIH prototype demonstration  
**Excluded:** Production certification and enterprise-wide discovery claims

## Frozen product claim

> ECDAT discovers cryptographic evidence in supported repository files, correlates that evidence into an inspectable inventory and CBOM, and prioritizes post-quantum migration using transparent risk context and Mosca-style planning scenarios.

ECDAT will not be presented as finding all cryptography, as universally accurate, as predicting the arrival of a cryptographically relevant quantum computer, or as equivalent in scope to IBM Quantum Safe Explorer or Keyfactor AgileSec.

## Phase 0 — Scope and evidence contract

Status: **complete**

- Repository-focused static discovery is the demonstration boundary.
- Coverage means supported-file processing coverage.
- Confidence means heuristic evidence confidence until real-world calibration exists.
- Precision and recall refer to the labelled evaluation corpus, not every scan.
- Mosca values are a modelled scenario with user-provided or policy-default inputs.
- Unsupported, unreadable and oversized files remain visible limitations.

## Phase 1 — Critical workflow stability

Status: **complete for the local SIH path**

Judge-facing workflow:

1. Sign in.
2. Enter a repository path.
3. Start the scan once.
4. Observe genuine indexing and collection progress.
5. Reach an explicit terminal state.
6. Open scan history.
7. Inspect scan metrics and failures.
8. Inspect individual findings.
9. Export reports and CBOM.

Exit gates:

- Backend health and readiness checks pass.
- Frontend is reachable.
- Repeated submission cannot create duplicate active jobs for the same repository.
- Scan status cannot remain indefinitely queued/running after worker failure.
- Cancelled, failed and timed-out states remain inspectable in history.
- One prepared positive repository completes through the live API.
- The completed scan persists in history and its detail endpoint works.
- The frontend unit, lint and browser workflow suites pass.
- The backend scan admission and lifecycle suites pass.

Gate evidence is recorded in `docs/SIH_PHASE_1_GATE_2026-09-22.md`.

### Phase 2 — Metric honesty

Status: **complete**

Make coverage, confidence, evaluation accuracy and Mosca provenance unambiguous throughout the UI and exports.

### Phase 3 — Detection precision

Status: **complete for the SIH corpus gate**

Reduce visible false positives, strengthen semantic/API context and validate the frozen corpus without regression.

### Phase 4 — Demonstration repositories

Status: **complete**

Prepare positive, negative-control and mixed-risk repositories with independently documented expected findings.

### Phase 5 — Mosca scenarios

Status: **complete**

Expose X, Y and Z, provenance, formula, result, and conservative/baseline/aggressive planning scenarios.

Gate evidence for Phases 2–5 is recorded in `docs/SIH_PHASES_2_TO_5_GATE_2026-09-22.md`.

## Remaining phases

### Phase 6 — Judge-facing interface

Status: **complete**

Polish the dashboard, inventory, finding detail, scan history and exports around the verified workflow.

### Phase 7 — Deployment packaging

Status: **complete, with live Docker execution blocked on this host**

Provide one reproducible local deployment path, health checks, migrations, account provisioning, persistence and recovery instructions.

Gate evidence for Phases 6–7 is recorded in `docs/SIH_PHASES_6_AND_7_GATE_2026-09-22.md`.

### Phase 8 — Verification

Run backend, frontend, browser, accessibility, responsive, corpus, migration and repeated-scan gates and record the evidence.

### Phase 9 — Presentation

Prepare the seven-minute demonstration, architecture explanation, limitations, competitor comparison and recorded fallback.

### Phase 10 — Final go/no-go

Approve the SIH build only when the complete workflow, positioning, test evidence and backup demonstration are ready.
