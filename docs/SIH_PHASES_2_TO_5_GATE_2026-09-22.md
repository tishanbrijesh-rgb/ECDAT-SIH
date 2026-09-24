# SIH Phases 2–5 Gate Evidence

**Date:** September 22, 2026  
**Scope:** SIH prototype, not production certification

## Phase 2 — Metric honesty

- “Supported-file coverage” means successfully processed eligible files; the UI states that it is not detection accuracy.
- “Evidence confidence” means strength of the collected evidence; it is not calibrated probability.
- Precision, recall and F1 are labelled as evaluation-corpus measurements and are shown only when labelled ground truth exists.
- Mosca inputs display policy-default or user-edited provenance on the finding detail page.

## Phase 3 — Detection precision

- Added a regression for algorithm-named configuration symbols in Python, JavaScript and Java.
- A symbol such as `ECDSA = object()` is no longer classified as an observed cryptographic operation.
- Frozen 53-case corpus gate passes: precision 85.71%, recall 96.00%, F1 90.57%, negative accuracy 100%.
- These figures describe only the included labelled corpus and must not be presented as universal accuracy.

## Phase 4 — Demonstration repositories

Fixtures live in `demo-repositories/` and carry independent `expected-findings.json` files.

| Fixture | Observed scan result | Gate |
|---|---|---|
| Positive control | AES, ECDSA, HMAC, RSA, SHA-256 | Pass |
| Negative control | No findings | Pass |
| Mixed risk | AES, ECDSA, MD5, RSA, SHA-1 | Pass |

## Phase 5 — Mosca scenarios

- X = data lifetime, Y = migration time, Z = modeled threat horizon.
- Decision formula is shown as `X + Y` versus `Z` with overlap or remaining margin.
- The selected baseline is accompanied by a conservative two-year migration overrun and an aggressive two-year migration acceleration (bounded to at least one year).
- Scenario labels avoid implying that ECDAT predicts the date of a cryptographically relevant quantum computer.

## Verification

- Frontend unit/component tests: **94 passed**.
- Frontend lint: **passed**.
- Frontend production build: **passed**.
- Backend precision, benchmark, corpus-detector and evaluation tests: **83 passed, 34 subtests passed**.
- Frozen corpus gates: **passed**.

## Remaining limitations

- Corpus accuracy is not real-world prevalence or production calibration.
- Dependency evidence may identify capability without proving runtime reachability.
- Static analysis cannot resolve every dynamic import, generated file, binary or runtime-only configuration.
- SIH deployment packaging, complete browser/accessibility verification and judge presentation remain in Phases 7–10.
