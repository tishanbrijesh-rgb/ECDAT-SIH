# ECDAT Sequential Repair and Verification Plan for Claude

## Objective

Repair ECDAT one defect group at a time. Do not attempt a broad rewrite. Every stage must be reproduced, fixed, tested, manually verified, and recorded before the next stage begins.

## Mandatory safety rules

1. Do not use Git commands, commits, resets, checkouts, rebases, cleaning, or stashing.
2. Preserve all existing work. Many files already contain uncommitted changes.
3. Do not delete, replace, or directly experiment on an important database.
4. Run backend tests against a disposable test database.
5. Never scan `C:\`, the user profile, system directories, or a directory outside the explicitly selected repository.
6. Begin scan testing with small controlled fixtures. Test the full repository only after all fixture scans pass.
7. Enforce file-count, file-size, evidence-count, memory, and duration limits during scan tests.
8. Do not expose credentials, authentication tokens, environment variables, or secret file contents.
9. Do not install dependencies unless they are genuinely required and the user approves.
10. For every behavioral fix:
    - Add or update a regression test that demonstrates the problem.
    - Run the narrow test and confirm the expected failure.
    - Apply the smallest coherent fix.
    - Run the narrow test again.
    - Run the related test group.
    - Manually verify the affected interface or API.
    - Record the result before continuing.
11. If a stage remains broken, stop there. Do not stack later changes on an unreliable foundation.
12. Do not claim completion because a page loads. Verify its data, interaction states, error states, accessibility, responsiveness, and performance.

## Stage 1 — Repair the backend test foundation

This stage comes first because later algorithm and API testing cannot be trusted while database fixtures are broken.

Known problems:

- `crypto_assets has no column named evidence_kind`
- `no such table: scan_jobs`
- Test database models and migrations are out of sync.
- The SSE endpoint test can hang indefinitely.

Tasks:

1. Identify every path used to create a backend test database.
2. Make tests create the current schema through one consistent mechanism.
3. Verify all migrations, including migration `0005`, from a new empty temporary database.
4. Remove test reliance on stale checked-in database files.
5. Bound the SSE test by consuming a known event sequence or applying a deterministic timeout.
6. Ensure every test closes streams, database sessions, workers, and temporary resources.

Exit criteria:

- No backend test hangs.
- Migration tests pass from an empty temporary database.
- API contract tests can create scans and assets.
- The full backend suite completes without schema errors.

## Stage 2 — Repair scan lifecycle reliability

Fix scan execution before changing detection or scoring algorithms.

Known problems:

- Cancellation, timeout, and launch-failure paths can subtract timezone-naive and timezone-aware timestamps.
- Failed jobs can remain queued or running.
- Large-scan behavior has not been proven under enforced limits.

Tasks:

1. Reproduce these paths independently:
   - successful completion
   - collector failure
   - launch failure
   - cancellation
   - timeout
   - forced worker termination
2. Normalize timestamps before duration calculations.
3. Guarantee that each scan reaches exactly one terminal state: `completed`, `failed`, `cancelled`, or `timed_out`.
4. Ensure workers, leases, locks, and database sessions are released on every path.
5. Return structured failure information instead of silently reporting zero assets.
6. Ensure progress counters are monotonic and internally consistent.
7. Include applied scan limits in the result metadata.
8. Report truncation and blind spots explicitly instead of presenting a partial scan as complete.

Exit criteria:

- Every lifecycle regression test passes.
- No orphaned worker, lease, or database lock remains.
- Failed scans cannot appear successful.
- Cancellation and timeout create the correct final status and explanation.

## Stage 3 — Prove large scans safely

Do not begin large-scan testing with the entire repository.

Test sequence:

1. A fixture containing approximately 10 supported files.
2. A fixture containing nested directories and ignored files.
3. A fixture containing 500–1,000 generated safe text files.
4. A fixture that exceeds the configured file limit.
5. A fixture containing an oversized file.
6. A fixture containing unreadable, binary, and malformed files.
7. A fixture containing symbolic links.
8. Only after all previous cases pass, scan the ECDAT repository itself using explicit limits.

Record for every scan:

- Files discovered
- Files in scope
- Files processed
- Files skipped
- Files failed
- Evidence records collected
- Findings produced after correlation
- Duration
- Peak memory when available
- Coverage percentage
- Truncation and blind spots

Exit criteria:

- Large scans finish or terminate cleanly within configured limits.
- The application remains responsive while a scan runs.
- Every skipped or failed file has a safe reason code.
- Result views use pagination or virtualization instead of creating enormous pages.
- Repeated scans of the same fixture produce deterministic results.

## Stage 4 — Correct severity and priority scoring

Do not manufacture HIGH or CRITICAL results merely to fill charts. Those labels must be produced by defensible risk inputs.

Current likely cause:

Every newly persisted finding receives the same business defaults:

- Business criticality: medium
- Data sensitivity: medium
- Exposure: internal
- Data lifetime: 10 years
- Migration time: 3 years
- Threat horizon: 15 years
- Migration effort: medium

These uniform inputs strongly constrain the severity distribution.

Tasks:

1. Separate these concepts in both code and presentation:
   - detection confidence
   - cryptographic weakness
   - quantum vulnerability
   - operational exposure
   - business impact
   - remediation urgency
2. Never derive risk severity from low detection confidence.
3. Define and document a bounded scoring table.
4. Add explicit risk rules for:
   - deprecated algorithms such as MD5 and SHA-1
   - weak key sizes and obsolete curves
   - confirmed RSA, ECDH, ECDSA, DH, or DSA usage
   - public or internet exposure
   - sensitive long-lived data
   - critical business systems
   - capability-only evidence
   - ambiguous or conflicting evidence
5. Keep unknown business context unknown, or identify a neutral policy default clearly.
6. Return structured reason codes and human-readable explanations for every score.
7. Create controlled fixtures that legitimately produce LOW, MEDIUM, HIGH, and CRITICAL results.
8. Add boundary tests for every severity threshold.

Exit criteria:

- All four labels are reachable through realistic controlled inputs.
- The same inputs always produce the same label and explanation.
- Detection confidence cannot accidentally become risk severity.
- Every HIGH or CRITICAL finding has auditable reasons.
- Dashboard, reports, graphs, CBOM, and inventory use the persisted risk label consistently.

## Stage 5 — Replace the false Mosca presentation

Mosca's inequality should describe whether migration must begin before a cryptographically relevant quantum computer becomes practical.

Model these inputs explicitly:

- `X`: required confidentiality lifetime
- `Y`: estimated migration time
- `Z`: estimated time until the threat becomes practical

Risk overlap exists when `X + Y >= Z`.

Tasks:

1. Stop presenting policy defaults as detected or measured facts.
2. Label each input as `detected`, `user-provided`, `policy-default`, or `unknown`.
3. Persist the value, unit, provenance, and last-update time for each input.
4. Do not claim an exact threat date without an identified policy or source.
5. Support uncertainty ranges where the data model permits them.
6. Recalculate immediately after the user changes an input.
7. Explain the calculation, assumptions, overlap result, and recommended action window.
8. Do not treat every cryptographic finding as quantum vulnerable.
9. Keep classical weakness, quantum exposure, and migration urgency separate.
10. Make recommendations depend on algorithm usage and protocol context, not only the algorithm name.

Exit criteria:

- Tests cover values below, equal to, and above the threat horizon.
- Missing inputs do not produce false certainty.
- The API and UI show the same calculation and provenance.
- User edits trigger deterministic recalculation.
- Recommendations match the actual cryptographic use case.

## Stage 6 — Enrich and validate the CBOM

Known problem:

The frontend validator expects snake_case fields while the API returns valid CycloneDX camelCase fields. This produces false schema errors.

Tasks:

1. Use CycloneDX 1.6 camelCase as the canonical export contract.
2. Correct frontend validation for `bomFormat`, `specVersion`, and `serialNumber`.
3. Use a real CycloneDX schema validator or a carefully tested minimal validator.
4. Never classify component risk from confidence.
5. Include useful cryptographic information when known:
   - algorithm
   - primitive and category
   - usage
   - key size or curve
   - protocol
   - library and package
   - source location
   - evidence source and evidence kind
   - confidence
   - quantum exposure
   - risk score and label
   - business context
   - Mosca inputs, provenance, and result
   - migration recommendation
   - parser and correlator version
6. Include component relationships and dependency information when supported by evidence.
7. Mark unavailable fields as unknown; never fabricate them.
8. Provide complete JSON export and scalable navigation for all components.
9. Validate the exported document using the same schema enforced in tests.
10. Ensure every component can be traced back to its source evidence.

Exit criteria:

- A valid API response displays `Valid CycloneDX`.
- Exported CBOM JSON passes schema validation.
- CBOM risk labels match the risk engine exactly.
- Every finding remains accessible even when the scan contains more than 250 components.
- A user can navigate from a CBOM component to its evidence.

## Stage 7 — Repair graph data before graph appearance

Tasks:

1. Define one graph contract containing:
   - stable node ID
   - node type
   - node label
   - edge source
   - edge target
   - edge relationship
2. Test the graph transformation without the UI.
3. Handle empty graphs, isolated nodes, duplicate nodes, cycles, missing targets, and large datasets.
4. Ensure severity charts use persisted risk labels.
5. Make graph and chart totals agree with Inventory, Reports, CBOM, and scan details.
6. Add legends, accessible labels, tooltips, and non-graph tabular alternatives.
7. Add bounded scrolling, zooming, filtering, aggregation, or clustering for large graphs.
8. Do not render raw object structures as a substitute for a functional graph.

Exit criteria:

- Controlled fixtures render the expected nodes and edges.
- Counts agree across every application view.
- Empty data produces a meaningful empty state.
- Large graphs do not freeze or overflow the page.
- Charts remain understandable without relying only on color.

## Stage 8 — Restore dark mode

Known problem:

`ThemeToggle` exists in `App.tsx` but is not rendered, and the application does not apply dark mode from system preference or stored preference.

Tasks:

1. Render an accessible theme control in the authenticated layout.
2. Support light, dark, and system preference.
3. Apply the theme before the first visual paint to prevent flashing.
4. Persist explicit user selection.
5. Test every main route in both themes.
6. Check contrast for text, charts, focus indicators, forms, badges, tooltips, tables, and code blocks.

Exit criteria:

- The document theme changes correctly.
- Refresh preserves an explicit selection.
- System preference works when no override exists.
- The dark-mode E2E test passes.
- No interface element becomes unreadable in either theme.

## Stage 9 — Repair responsive layout

Required test widths:

- 375px
- 390px
- 768px
- 1024px
- 1280px
- 1440px

Tasks:

1. Make mobile navigation collapsed by default.
2. Prevent navigation from covering page content.
3. Add `min-width: 0` to grid and flex children that must shrink.
4. Replace rigid six-column KPI layouts with responsive grids.
5. Give wide tables controlled horizontal scrolling within their own containers.
6. Ensure graph and chart canvases cannot exceed their containers.
7. Wrap long paths, evidence strings, serial numbers, and identifiers safely.
8. Paginate or virtualize large finding collections.
9. Correct the concatenated Mosca text on Asset Detail.
10. Consolidate duplicate or conflicting responsive CSS only after visual regression tests exist.

Exit criteria:

- `document.documentElement.scrollWidth <= document.documentElement.clientWidth` on normal pages.
- No card, chart, control, or text is clipped.
- Navigation works with touch and keyboard.
- Scan Detail remains usable with hundreds of findings.
- Every interactive control is reachable at 375px.

## Stage 10 — Repair counters, motion, rendering, and build performance

Tasks:

1. Fix the animated counter so its effect does not restart on every displayed frame.
2. Never display negative intermediate values for non-negative metrics.
3. Respect reduced-motion preferences.
4. Remove unnecessary perpetual animation from large result collections.
5. Avoid mounting hundreds of animated cards simultaneously.
6. Paginate, virtualize, or progressively disclose large report and CBOM datasets.
7. Consolidate duplicated CSS carefully.
8. Bring the CSS output under the configured production budget, or document and justify a deliberately revised budget.

Exit criteria:

- Counters remain valid and progress monotonically.
- Reduced-motion mode disables nonessential motion.
- The production frontend build passes.
- Reports and CBOM no longer create extremely tall, slow pages.
- Scrolling remains responsive with the large controlled fixture.

## Stage 11 — Repair accessibility and workflow tests

Tasks:

1. Make the Repository path label target the actual input instead of a surrounding group.
2. Update stale E2E selectors and wording only after confirming intended product copy.
3. Restore the accessibility harness dependency in the controlled test environment.
4. Test keyboard-only navigation, visible focus, the skip link, heading order, form labels, error announcements, dialogs, menus, chart alternatives, contrast, and reduced motion.
5. Use accessible roles and names in E2E tests rather than fragile CSS selectors.

Exit criteria:

- No serious or critical automated accessibility findings remain.
- Login, scan creation, inventory filtering, asset editing, export, navigation, theme selection, and logout work by keyboard.
- E2E tests describe current intentional workflows.

## Stage 12 — Final audit matching the tester workflow

Run this audit only after every earlier stage passes:

1. Start the application cleanly.
2. Test an invalid login.
3. Log in using the provisioned local account without printing credentials.
4. Visit every main route.
5. Inspect browser console errors and failed network requests.
6. Run a small controlled scan.
7. Run severity fixtures covering all four labels.
8. Run cancellation, timeout, and failure fixtures.
9. Run the bounded large fixture scan.
10. Run a bounded full ECDAT repository scan last.
11. Verify Inventory totals, filters, search, sorting, and pagination.
12. Open representative LOW, MEDIUM, HIGH, and CRITICAL assets.
13. Verify Mosca calculations manually against displayed inputs and provenance.
14. Validate the complete CBOM JSON against CycloneDX 1.6.
15. Verify graph node, edge, and severity totals.
16. Test every export and inspect its contents.
17. Test light, dark, and system themes.
18. Test every required viewport width.
19. Test keyboard-only and reduced-motion behavior.
20. Run the frontend unit tests, lint, production build, browser E2E tests, backend suite, migration tests, and accessibility checks.

## Final acceptance conditions

Do not report that the repair is complete unless:

- The frontend production build passes.
- Frontend unit tests pass.
- Browser E2E tests pass without hanging.
- Backend tests pass without excluding tests.
- Database migrations succeed from an empty database.
- Large scans complete or terminate safely within configured limits.
- All severity bands are produced by legitimate fixtures.
- Mosca calculations expose their assumptions and provenance.
- CBOM schema validation passes.
- Graph totals agree with the underlying data and other views.
- No tested page overflows at supported widths.
- Light, dark, and system themes work correctly.
- No serious or critical accessibility problems remain.
- No unexpected console errors or failed requests appear.
- The final report lists every executed command, test count, scan metric, known limitation, and remaining risk.

## Required final report format

For every stage, report:

1. Defect reproduced
2. Root cause
3. Files changed
4. Regression tests added or updated
5. Narrow verification result
6. Related-suite result
7. Manual verification result
8. Remaining limitations

End with one unambiguous release verdict: `READY`, `READY WITH DOCUMENTED LIMITATIONS`, or `NOT READY`.
