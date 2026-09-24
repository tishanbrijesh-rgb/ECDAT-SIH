# Phase 4 Progress — 2026-09-20

## Current checkpoint

Phase 4 is complete. Its architecture, corpus reproducibility, static-analysis,
backend, frontend, and browser gates are green.

## Completed

### WP-4.1 — Correlator v3 consolidation

- Removed the competing v2-postprocessing implementation and lazy proxy.
- Both public v3 entry points now resolve to one canonical function.
- Added golden coverage for entry-point identity, immutable input, ambiguity,
  cross-kind links, and moved-line annotations.
- Split the canonical correlator into preparation, grouping, link, ambiguity,
  context, and output-building helpers.
- Reduced canonical `correlate` complexity from 22 to below 10.
- Raised focused branch coverage to 87.3%, exceeding the 85% target.

### WP-4.2 — Priority hotspots

- Replaced `ast_collector.visit_Call`'s large branch chain with isolated hashlib,
  HMAC, and table-driven call classification.
- Split `scan_with_metrics` into budget checking, per-path collection,
  blind-spot construction, and failure-payload helpers.
- Both named hotspots now pass Ruff's complexity-10 gate.

## Verification

- Backend: 411 passed, 4 skipped, 92 subtests passed.
- Focused correlator tests: 30 passed plus 18 subtests.
- Correlator v3 branch coverage: 87.3%.
- Scanner safety/performance tests: 35 passed, 2 skipped.
- Ruff: passed.
- Mypy: passed across 89 source files.

### WP-4.2 — Runtime boundaries and large files

- Extracted typed evaluation operations and bounded ground-truth validation.
- Extracted pure Maven, npm, Gem, Go, and Cargo dependency parsers behind the
  existing collector interface; all four dependency parser complexity warnings
  are removed.
- Extracted database readiness and observability routes from `backend/main.py`.
- Reduced the tracked large files from 2,857 to 1,493 total lines; the corpus
  generator fell from 1,198 to 77 lines.
- Reduced the project-wide C901 inventory from 18 to 12. The remaining warnings
  are recorded technical debt; the Phase 4 priority functions (`correlate`,
  `visit_Call`, `scan_with_metrics`, readiness, ground-truth loading, and the
  dependency parsers) now meet the complexity gate. The standard Hungarian
  assignment routine remains intentionally isolated and unchanged.

### WP-4.3 — Reproducible corpus tooling

- Replaced the repetitive corpus generator with a declarative combined-manifest
  source and deterministic split generation.
- Added `--check` drift detection and a regression test that compares every
  generated payload with its committed manifest.
- Preserved all 333 entries and exact committed JSON serialization.

## Final verification

- Backend: 412 passed, 4 skipped, 92 subtests passed.
- Ruff: passed for normal lint rules.
- Mypy: passed across 94 source files.
- Corpus regeneration check: passed.
- Frontend: lint and formatting passed; 86 unit tests passed; production build passed.
- Browser workflows: 58 passed across responsive, accessibility, and core flows.

## Deferred to Phase 5 / maintenance backlog

- Twelve non-blocking complexity warnings remain in older retry, output, v2
  correlation, supervision, settings, certificate, rule, and corpus-validator
  paths. They are not hidden or globally suppressed.
