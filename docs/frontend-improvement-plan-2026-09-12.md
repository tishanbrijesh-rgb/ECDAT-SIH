# ECDAT Frontend Improvement Plan

## Product direction

ECDAT should feel like a focused security tool made for people who need to answer three questions quickly:

1. What cryptography do we have?
2. What needs attention first?
3. What should I do next?

The interface should be calm, direct, and practical. Keep the existing warm neutral palette and forest-green accent, but remove unfinished visual fragments, oversized empty areas, technical language that does not help decisions, and repeated card decoration. The result should feel authored by a security product team rather than assembled from dashboard templates.

## Design principles

- Prefer plain labels: “Overview”, “Inventory”, “New scan”, “Reports”, and “CBOM” are good; explain specialist terms where they first appear.
- Put the most useful action beside the information it affects.
- Use one primary action per view and make secondary actions visually quieter.
- Use cards only for true groups; use spacing, headings, dividers, and tables for the rest.
- Use real scan data and natural copy. Do not add decorative fake metrics, generic marketing text, gradients, glowing elements, or excessive animation.
- Keep motion short and purposeful: page fade, expanding disclosure, toast, and progress changes. Respect reduced-motion preferences.
- Use Geist/Satoshi-style sans typography with a monospace face only for paths, hashes, IDs, and measured values.
- Meet WCAG 2.2 AA, support keyboard use, and maintain usable layouts from 320px mobile through wide desktop.

## Phase F1 — Repair the information architecture (P0)

### Global shell

- Keep the five primary destinations, but visually group “Overview / Inventory / Reports / CBOM” as review work and make “New scan” the distinct primary action.
- Replace the text-heavy brand lockup with a compact logo and product name; move “Discovery Assurance” into an unobtrusive subtitle or tooltip.
- Turn “Local & explainable” into a small system-status control showing API, database, and scanner health instead of a decorative badge.
- Put account/sign-out actions into a compact user menu; keep theme selection beside it.
- Make the header responsive: desktop navigation, mobile menu, no clipped labels or horizontal scrolling.
- Use one consistent content width and vertical rhythm on every page.

### Page hierarchy

- Every page gets: eyebrow/context, clear H1, one-sentence purpose, primary action, then content.
- Remove large empty areas that push important content below the fold.
- Use consistent breadcrumbs only on detail pages, not top-level pages.

Acceptance: users can identify the current page and its primary action within three seconds at desktop and mobile widths.

## Phase F2 — Make Overview decision-oriented (P0)

- Replace generic metric cards with a compact assurance summary:
  - latest scan status and time;
  - confirmed cryptographic operations;
  - capability-only findings;
  - migration priorities;
  - scan coverage and failures.
- Add a “Needs attention” section showing the five highest-priority findings with algorithm, location, reason, confidence, and direct link.
- Show risk distribution and evidence composition as small readable visuals with adjacent values; never require hover to understand them.
- Add a recent-scans timeline with status, repository, duration, coverage, and findings.
- Give first-time users one clear empty-state action: “Run your first scan.”
- When the API fails, show an inline recovery panel with retry, readiness status, request ID, and a useful cause such as “database migration required.”

Acceptance: the Overview answers “what changed and what needs attention?” without visiting another page.

## Phase F3 — Simplify Inventory (P0)

- Default to a readable table; keep alternate views only if they provide a real workflow benefit.
- Group controls into one toolbar: search, risk, evidence type, algorithm, repository/scan, and sort.
- Replace the unclear “Quantum vulnerable” text control with an explicit checkbox or filter chip showing its active state.
- Show active filters as removable chips and provide “Clear all.”
- Use human column names: Finding, Evidence, Location, Confidence, Priority, Action.
- Distinguish confirmed use from declared capability with text and shape, not color alone.
- Keep row actions concise: “View details” as the row link; place editing/export actions in a contextual menu.
- Add pagination or virtualization for large scans, sticky table headers, truncation with accessible full-value disclosure, and a compact mobile list layout.
- Do not show “No assets found” while an API error is active. Error, loading, empty, and filtered-empty states must be mutually exclusive.

Acceptance: a user can find a vulnerable confirmed operation and open its evidence in under four interactions.

## Phase F4 — Rebuild New Scan as a clear three-step task (P0)

- Replace broken text such as `01Enumerate scope` and `1Repository` with properly styled numbered steps.
- Keep the step indicator visually separate from explanatory copy.
- Step 1: repository path, recent-path suggestions, validation, allowed-root guidance.
- Step 2: scan options with safe defaults and plain explanations; hide advanced limits in a disclosure.
- Step 3: review repository and options, then “Start scan.”
- Validate each field inline and never advance when invalid.
- During scanning, replace the form with live progress: current phase, files processed, findings, elapsed time, cancel action, and declared blind spots.
- On completion, show a concise result summary with “View inventory” as primary and “View report” as secondary.
- Recent scans should be a compact table below the task, not visually compete with the scan form.

Acceptance: a first-time user can launch `/test-repo` without needing documentation, and every scan state has a clear next action.

## Phase F5 — Make Reports and CBOM understandable (P1)

### Reports

- Add a report header with scan selector, generated time, export actions, and an explanation of observed operations versus declared capabilities.
- Lead with ranked migration priorities, not an abstract score.
- Each priority explains: why it matters, supporting evidence, recommended replacement, migration effort, and affected location.
- Put evaluation metrics in a clearly labeled “Detection quality” section; distinguish corpus benchmarks from the current repository’s reviewed ground truth.
- Replace blank error screens with retryable panels that preserve the page structure.

### CBOM

- Start with a concise inventory summary and component table.
- Keep Components, Dependency graph, and Raw JSON as clear tabs with counts.
- Make graph controls discoverable and provide a table fallback for keyboard/mobile users.
- Put CycloneDX/JSON export near the page title and state exactly which scan is exported.
- Explain CBOM once in plain language: “A machine-readable inventory of cryptographic components and evidence.”

Acceptance: non-specialists can understand what the report says; specialists can reach raw evidence and exports without losing context.

## Phase F6 — Create a small, coherent design system (P1)

- Consolidate the overlapping CSS files into tokens, base, components, layouts, and page-specific styles.
- Remove duplicate selectors and specificity overrides that caused the login and scan-step regressions.
- Standardize spacing, content widths, typography, borders, radii, shadows, focus rings, buttons, inputs, tables, badges, disclosures, and alerts.
- Keep one accent color and semantic colors for risk/status. Verify light and dark contrast independently.
- Use one icon family only after confirming it is installed; otherwise use simple local SVGs.
- Document component states in a lightweight internal showcase or Storybook-equivalent test page.
- Keep animations limited to transform and opacity and isolate Framer Motion to components that benefit from it.

Acceptance: pages no longer depend on import order accidents, and common components look and behave identically everywhere.

## Phase F7 — Complete accessibility, responsive, and performance QA (P1)

- Test keyboard order, skip link, visible focus, dialogs, disclosures, tables, form errors, toast announcements, and charts.
- Run authenticated Axe checks on every populated route in light and dark modes.
- Validate 320, 375, 768, 1024, 1440, and 1920px widths with no horizontal overflow.
- Add visual regression snapshots for loading, empty, populated, filtered-empty, validation, API error, scan-running, and scan-complete states.
- Replace generic spinners with layout-matched skeletons where content shape is known.
- Lazy-load report charts and raw CBOM views; keep initial interaction fast.
- Resolve the Windows Playwright shutdown leak so E2E returns a clean exit code.

Acceptance: WCAG 2.2 AA automated checks have no serious violations, all target widths pass, and the production bundle stays inside existing budgets.

## Delivery sequence

1. Global shell and design-system cleanup.
2. New Scan workflow.
3. Overview and Inventory.
4. Reports and CBOM.
5. Accessibility, responsive, visual-regression, and performance gates.
6. Continue with the backend/scanner roadmap in `implementation-improvement-plan-2026-09-12.md`.

## Definition of done

- All top-level routes have polished loading, populated, empty, and error states.
- No raw API error string is the only content on a page.
- No broken counters, joined labels, clipped controls, or contradictory states.
- Primary tasks are usable with keyboard and at 375px.
- UI tests, E2E workflows, authenticated accessibility checks, build, lint, formatting, and performance budgets pass.
- Five people unfamiliar with ECDAT can start a scan and identify the highest-priority finding without coaching.

