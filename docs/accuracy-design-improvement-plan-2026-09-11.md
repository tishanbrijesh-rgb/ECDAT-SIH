# ECDAT accuracy and product-design improvement plan

**Prepared:** 2026-09-11  
**Starting branch:** `fix/sha1-recommendation`  
**Status:** Phase 1 complete (2026-09-11). v2 operation-level evaluation merged.

## Phase 1 completion summary

All six implementation tickets delivered:

| Ticket | Status | Key files |
| --- | --- | --- |
| Lockfile names in `_inventory()` + regression tests | Complete | `scanner/collectors/registry.py`, `tests/test_scanner.py` |
| Shared collector registry | Complete | `scanner/collectors/registry.py` |
| Operation-level evaluation with legacy backward compat | Complete | `backend/services/evaluation.py` (v2 at line 549) |
| Duplicate predictions as FP + joint metadata matching | Complete | `_operation_match_score()`, `_hungarian_match()` |
| Per-language, per-collector metric slices | Complete | `per_source`, `blind_spots`, `failures` in v1/v2 |
| Versioned evaluator schema | Complete | `"evaluation_version"` field in ground truth + return dict |

**Exit gates met:**
- A correct algorithm at the wrong operation scores as a miss (cross-component pairs rejected post-Hungarian).
- All 177 tests pass (41 v2-specific tests, 136 v1/regression tests).
- v1 behavior preserved: ground truth without `"evaluation_version": 2` uses original set-based matching.
- `operation_findings` field present in both v1 and v2 return dicts.

**Unresolved:** None. All six implementation tickets and exit gates fully complete.

## 1. Outcome

Improve ECDAT in two linked ways:

1. Make discovery accuracy credible beyond the bundled demonstration by measuring operation identity, usage, key size, provenance, and negative cases on frozen, unconsumed corpora.
2. Turn the dashboard into an evidence-first analyst console that makes certainty, coverage, blind spots, and migration actions understandable without overstating assurance.

The target is not a visually impressive demo with a nominal 100% score. The target is a reproducible system whose claims are scoped, whose mistakes are inspectable, and whose interface helps an analyst decide what to verify next.

## 2. Verified starting point

- Scanner sources: Python AST, multi-language rules, dependency manifests, and X.509 certificates.
- Pipeline: collection → operation-aware correlation (`operation-v2`) → confidence → risk → persistence → API/UI.
- Current regression state: 118 backend tests, 22 frontend tests, and 7 Chromium workflows were reported passing on 2026-09-10/11.
- Current backend coverage is reported as 84.95%.
- The external v3 result is 8 TP, 0 FP, and 0 FN, but it is a consumed Java/SHA holdout with only eight positive operations.
- The built-in evaluator compares only `(component, algorithm)` pairs. It does not validate operation identity, usage, key size, source location, or duplicate findings.
- Confidence weights are hand-set constants rather than calibrated probabilities.
- The UI is functional and responsive, with dark mode, motion reduction, loading/empty/error states, CBOM, evidence, risk, and evaluation views.

## 3. Important findings to address first

### Accuracy

1. **Unreachable lockfile collectors:** `scanner/main.py` has handlers for `package-lock.json`, `Gemfile.lock`, `go.sum`, and `Cargo.lock`, but `_inventory()` does not include them in the supported-file set. These handlers therefore never run through the main scanner.
2. **Capability and observed use are conflated:** imports and dependencies can become cryptographic findings even though they prove availability, not execution.
3. **Certificate role is inferred from key type:** an RSA public key is labeled encryption and an EC public key signature, although a certificate alone does not prove the operation.
4. **Dependency suppression can hide valid evidence:** dependency algorithms are dropped when stronger evidence finds different algorithms in the same component.
5. **Evaluation is too coarse:** component–algorithm matching can hide wrong locations, duplicated operations, wrong usage, and missing key sizes.
6. **Confidence is not calibrated:** fixed collector strengths plus bonuses produce an evidence score, not an empirically validated probability.
7. **Language depth is uneven:** Python hashes have binding-aware AST handling; most other languages rely on heuristic rules.

### Product design

1. The overview leads with six similar stat cards instead of an analyst decision hierarchy.
2. Risk, confidence, and coverage are visually adjacent enough to be confused even though they mean different things.
3. Evidence provenance and uncertainty are available but require too much navigation and reading.
4. The UI uses several competing accents (`teal`, `indigo`, `violet`, amber/red status colors), reducing hierarchy.
5. Styling is split across many cascade-dependent CSS files, increasing duplication and regression risk.
6. Navigation becomes a horizontally scrolling row on small screens rather than a deliberate mobile navigation pattern.
7. Several generic spinner/loading screens remain; skeletons do not consistently match final layouts.
8. Dense tables and evidence records need stronger scanning, filtering, comparison, and keyboard behavior.

## 4. Success metrics

Record a baseline before changing detectors. Do not retroactively edit a frozen corpus to retain a preferred score.

| Area | Metric | Release target |
| --- | --- | --- |
| Detection | Precision on each new unconsumed corpus | ≥ 95% |
| Detection | Recall on each new unconsumed corpus | ≥ 90% |
| Detection | Operation duplicate rate | ≤ 2% |
| Metadata | Usage accuracy over expected labels | ≥ 90% |
| Metadata | Known key-size accuracy over expected labels | ≥ 90% |
| Correlation | Identity/order determinism | 100% in regression suite |
| Coverage | Supported-file failures represented | 100% |
| Calibration | Brier score / expected calibration error | Baseline first; improve without precision loss |
| Performance | 10k-file source scan | Budget established in Phase 0; no >10% regression |
| Accessibility | Automated WCAG checks | 0 serious/critical violations |
| UX | Primary tasks | Scan, investigate, export in ≤ 3 navigation transitions each |
| Frontend | Core Web Vitals on reference hardware | LCP < 2.5 s, INP < 200 ms, CLS < 0.1 |
| Quality | CI | Backend, frontend, E2E, benchmark, schema, and accessibility gates pass |

Report micro- and macro-averages by language, collector, algorithm family, and evidence type. When a denominator is absent, report “not available,” never 100%.

## 5. Delivery plan

### Phase 0 — Freeze baselines and contracts (1–2 days, P0)

**Accuracy work**

- Capture current benchmark outputs, timings, memory, finding counts, and per-source counts as versioned artifacts.
- Define an operation-level label schema: repository revision, file hash, location/range, algorithm, usage, key size, evidence class, and expected blind spot.
- Split datasets into `regression`, `development`, and sealed `holdout`; record when a holdout becomes consumed.
- Add benchmark metadata validation and an explicit taxonomy/allowlist for every corpus.
- Define capability, declaration, configuration, and observed-operation evidence classes.

**Design work**

- Inventory routes, states, components, tokens, breakpoints, and duplicated CSS selectors.
- Capture reference screenshots at 375, 768, 1280, and 1440 px in light/dark and reduced-motion modes.
- Run keyboard-only and automated accessibility audits.
- Write a one-page design brief: “quiet forensic workspace,” not marketing dashboard.

**Exit gate**

- Baselines are reproducible from one command.
- Metrics include operation, usage, and key-size accuracy.
- Current UI has screenshot and accessibility baselines.

### Phase 1 — Correct the measurement and ingestion foundation (2–3 days, P0)

**Implementation tickets**

1. Add all implemented lockfile names to `_inventory()` and regression-test that each main-path handler executes.
2. Replace hard-coded filename checks with a shared collector registry declaring supported names/extensions and handler ownership.
3. Upgrade `ground_truth.json` and `evaluate_assets()` to operation-level matching while retaining a labeled legacy component-level view.
4. Count duplicate predictions as false positives and jointly match algorithm, usage, and key-size metadata.
5. Expose per-language, per-collector, positive, negative, malformed, and unavailable metric slices.
6. Version the evaluator schema and persist detector/rule/correlation versions with every scan.

**Tests**

- Positive, negative, duplicate, moved-line, malformed-label, unsupported-taxonomy, and missing-key-size cases.
- Contract tests for evaluation API and dashboard types.

**Exit gate**

- A correct algorithm at the wrong operation can no longer score as fully correct.
- Lockfile scans produce evidence through `scan_with_metrics()`.

### Phase 2 — Separate evidence semantics (3–5 days, P0)

Introduce an explicit evidence model:

- `observed_operation`: direct call/configuration selecting an algorithm.
- `declared_capability`: dependency or import that can provide cryptography.
- `configured_protocol`: TLS/cipher/certificate configuration.
- `artifact_metadata`: certificate/key metadata without inferred runtime use.
- `unknown`: retained but not promoted.

**Changes**

- Stop treating imports alone as observed operations.
- Preserve dependencies even when a different strong algorithm is observed; rank them as capability evidence rather than deleting them.
- Change certificate usage to `unknown` unless EKU, key usage, protocol configuration, or call-site evidence establishes a role.
- Carry `evidence_kind`, parser/rule version, exact span, and confidence reasons into persistence, CBOM, risk reports, and APIs.
- Ensure risk scoring distinguishes confirmed use from capability-only exposure.

**Exit gate**

- No capability-only record is presented as a confirmed runtime operation.
- Existing evidence remains inspectable; nothing is silently discarded.

### Phase 3 — Build genuinely independent corpora (4–6 days, P0/P1)

Create frozen corpora before detector work:

- Languages: Python, Java, JavaScript/TypeScript, C/C++, Go, and C#.
- Families: hashing/MAC, symmetric encryption/AEAD, signatures, key establishment, TLS, KDFs, RNG, certificates, and PQC.
- Sources: at least three unrelated repositories per major language group, pinned by commit and file hash.
- Cases: direct calls, aliases, wrappers, constants, comments, strings, dead code, dynamic selection, malformed files, dependency-only declarations, and negative repositories.

Use two-person or independent-agent review for labels. Keep the final holdout inaccessible to detector authors until a candidate is frozen.

**Exit gate**

- At least 150 positive operations and 150 meaningful negatives across at least four languages for the first broad benchmark.
- Label review, provenance, taxonomy, and consumption status are recorded.

### Phase 4 — Improve detector depth in precision-first slices (1–2 weeks, P1)

Deliver one language/family slice per pull request, each starting with frozen fixtures.

1. **Python:** extend binding-aware AST analysis to cipher constructors, asymmetric operations, KDFs, TLS contexts, aliases, and simple constant propagation.
2. **Java:** replace the most fragile regex paths with parser-backed call and selector extraction; resolve common JCA/Bouncy Castle wrappers conservatively.
3. **JavaScript/TypeScript:** parse Node `crypto`, WebCrypto, TLS configuration, and imports without matching strings/types/comments.
4. **Go:** parse `crypto/*`, TLS configuration, and explicit key sizes/curves.
5. **C/C++ and C#:** add parser-backed high-value APIs first; keep unsupported dynamic cases as blind spots.
6. **Dependencies:** parse implemented lockfiles, resolved versions, direct/transitive status, and advisory evidence without claiming use.
7. **Certificates:** add validity, signature algorithm, key strength, KU/EKU, CA role, SAN summary, and chain-position evidence.

**Per-slice gate**

- Positive, negative, alias, wrapper, malformed, duplicate, and performance tests pass.
- Precision does not fall below 95% on any established corpus.
- New blind spots are documented before merge.

### Phase 5 — Correlation and confidence calibration (3–5 days, P1)

- Introduce `operation-v3` identity based on normalized spans and semantic anchors, with explicit moved-line behavior.
- Add conservative cross-collector matching rules instead of requiring exact existing anchors or merging by proximity.
- Model multiple plausible matches as ambiguity, not arbitrary selection.
- Replace hand-written confidence interpretation with calibrated bands derived from labeled development data.
- Keep the raw evidence score and calibrated probability separate.
- Measure reliability diagrams, Brier score, and expected calibration error.
- Version calibration parameters and add drift checks.

**Exit gate**

- Input order never changes IDs or context.
- Confidence labels have measured calibration evidence and are not presented as certainty.
- Correlation gains recall without exceeding the precision floor.

### Phase 6 — Establish the design system (3–4 days, P1)

Use a technical-console direction with design variance 6, motion 3, and visual density 7—more restrained than the generic high-motion skill baseline because this is an analyst tool.

**Foundation**

- Consolidate tokens for neutral surfaces, one teal action accent, semantic risk colors, typography, spacing, radii, shadows, focus, and motion.
- Keep risk colors semantic only; remove decorative indigo/violet competition.
- Use a dashboard-appropriate sans/mono pairing and tabular numerals; validate font loading and fallback behavior.
- Standardize iconography with one verified icon package or a small shared SVG set; remove decorative Unicode symbols.
- Reduce CSS cascade ambiguity by organizing layers into tokens, primitives, components, pages, and utilities.
- Create shared primitives: page header, metric, disclosure, data table, filter bar, status, skeleton, empty/error state, drawer, dialog, and evidence badge.
- Default motion to transform/opacity, support reduced motion, and avoid perpetual animation on data-heavy screens.

**Exit gate**

- Story/demo route covers every component state in light/dark/mobile modes.
- Focus contrast and color contrast meet WCAG AA.
- No page invents a new spacing, color, or status treatment without a token.

### Phase 7 — Redesign workflows, not decoration (5–7 days, P1)

**Overview**

- Replace six equal stat cards with a hierarchy: posture summary, urgent actions, assurance quality, then supporting trends.
- Visually separate “risk,” “confidence,” and “coverage” with definitions and drill-downs.
- Show scan scope and benchmark provenance near any accuracy metric.

**Inventory**

- Add a sticky filter/sort bar, column visibility, saved filters, bulk export, dense/comfortable modes, and a mobile card/list fallback.
- Make algorithm, usage, evidence kind, confidence band, risk, and source location scannable without opening every row.

**Asset/evidence detail**

- Use an evidence timeline showing claim → supporting evidence → ambiguity/conflict → risk reasoning → recommendation.
- Put raw evidence in progressive disclosure with copy/download controls.
- Clearly label capability-only and unknown-use records.

**Scan workflow**

- Replace indeterminate progress with collector/file progress from SSE, reconnect state, elapsed time, cancel state, and partial-failure summary.
- Provide a post-scan completion panel before redirect rather than relying only on a toast.

**CBOM and reports**

- Use actual persisted risk labels for risk distribution; never derive “critical” from low confidence.
- Add schema-validation status, export provenance, and filters for evidence kind and uncertainty.
- Present migration actions as an ordered work queue with reasons, dependencies, and analyst acknowledgement.

**Navigation/mobile**

- Replace horizontal nav overflow with a deliberate compact navigation control below 760 px.
- Preserve scan context visibly across routes.
- Ensure tables, charts, dialogs, and disclosures work at 320–375 px and 200% zoom.

**Exit gate**

- Scan → investigate unexpected finding → inspect evidence → export report is keyboard-complete.
- Empty, loading, partial, stale, disconnected, error, and success states are tested for every data route.

### Phase 8 — Verification, rollout, and observability (2–3 days, P0)

- Add CI jobs for broad benchmarks, schema validation, visual regression, axe accessibility, frontend unit coverage, and Playwright desktop/mobile projects.
- Add performance budgets for scanner time/memory and dashboard bundles/Web Vitals.
- Run old and new detector/correlation versions side by side on the development corpus; publish the delta.
- Gate new semantics behind versioned APIs or a feature flag if existing persisted scans cannot be migrated safely.
- Rescan fixtures; do not rewrite historical results silently.
- Ship in small releases with rollback points and release notes that distinguish measured gains from assumptions.

## 6. Pull-request sequence

| PR | Scope | Depends on |
| --- | --- | --- |
| 1 | Scanner registry + reachable lockfile handlers + tests | None |
| 2 | Operation-level evaluation schema and matcher | PR 1 |
| 3 | Evidence-kind model across scanner, DB/API, and exports | PR 2 |
| 4 | Certificate semantics and dependency retention | PR 3 |
| 5 | Broad corpus tooling and first frozen corpus | PR 2 |
| 6+ | One detector language/family slice per PR | PRs 3 and 5 |
| 7 | Calibration baseline and confidence API contract | PRs 2 and 5 |
| 8 | Design tokens and shared UI primitives | Can run after PR 3 contract stabilizes |
| 9 | Overview + evaluation redesign | PRs 7 and 8 |
| 10 | Inventory + evidence-detail redesign | PRs 3 and 8 |
| 11 | Scan + CBOM/report redesign | PRs 3, 4, and 8 |
| 12 | Visual/a11y/performance gates and rollout | PRs 9–11 |

## 7. Test matrix

### Scanner and evaluation

- Unit: parser helpers, bindings, selectors, key sizes, KU/EKU, manifests, confidence math.
- Property-based: path normalization, input order, duplicate evidence, identity stability, redaction.
- Metamorphic: comments/whitespace/renames should not change semantics; changing an algorithm selector should.
- Differential: old versus new detector outputs with reviewed deltas.
- Corpus: frozen positive/negative/malformed cases and sealed holdout.
- Performance: file count, bytes, evidence count, time, and memory budgets.

### Frontend

- Component: loading, empty, partial, error, stale, disconnected, success, and permission states.
- Contract: runtime schema validation for critical API responses.
- E2E: analyst, admin, viewer, and auditor workflows.
- Accessibility: keyboard, focus order, screen-reader names, contrast, 200% zoom, reduced motion.
- Visual: four viewport widths × light/dark × representative data states.
- Performance: bundle diff, route lazy-loading, render count, chart/table responsiveness.

## 8. Definition of done for every increment

- A failing regression or frozen fixture exists before a detector fix.
- Precision, recall, metadata accuracy, duplicates, and performance deltas are reported.
- Findings retain provenance, scope, versions, and human-readable reasons.
- API/types/docs/exports/UI change together when semantics change.
- Unit, integration, E2E, formatting, lint, accessibility, and relevant benchmark gates pass.
- No metric is presented without its granularity, corpus, denominator, and consumption status.
- UI changes include mobile, dark, loading, empty, error, and reduced-motion states.
- The change is small enough to revert independently.

## 9. Risks and controls

| Risk | Control |
| --- | --- |
| Optimizing to a tiny benchmark | Sealed holdout, corpus diversity, consumption labels |
| Recall gains create false positives | Precision floor and negative-heavy tests |
| Parser expansion becomes unbounded | Language/family slices and explicit blind spots |
| Confidence is mistaken for probability | Separate evidence score from calibrated probability |
| Historical scan meaning changes | Versioned semantics; rescan instead of silent rewrite |
| UI polish hides uncertainty | Put provenance, scope, and gaps beside headline metrics |
| Design rewrite causes regressions | Shared primitives, screenshot baselines, incremental page rollout |
| Motion harms usability/performance | Motion intensity 3, reduced-motion tests, transform/opacity only |

## 10. First implementation sprint

The first sprint should contain only these four deliverables:

1. Fix unreachable lockfile scanning through a collector registry and add main-path regression tests.
2. Implement the versioned operation-level evaluation schema and joint matcher.
3. Produce the first new frozen multi-language corpus before changing corresponding detectors.
4. Create the design-token audit and redesign the overview around risk actions, assurance quality, and explicit metric provenance.

This order prevents UI claims from outrunning measurement and prevents detector changes from consuming the new holdout before it is frozen.
