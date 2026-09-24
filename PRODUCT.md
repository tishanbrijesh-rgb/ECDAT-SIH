# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary users are security analysts and cryptographic migration owners operating ECDAT against local source repositories. They need to start a scan quickly, understand what was actually inspected, and decide which cryptographic findings deserve attention. Auditor and viewer roles consume the same evidence without write access. The primary-user emphasis is inferred from the repository roles and the requested scan-first workflow.

## Product Purpose

ECDAT discovers cryptographic assets in source repositories, correlates evidence from multiple detectors, ranks migration risk, and produces an evidence-backed cryptographic inventory and CBOM. Success means an operator can launch a scan without specialist setup, distinguish measured risk from missing context, and verify the quality of detection results.

## Positioning

ECDAT connects every risk decision to inspectable source evidence and reports evaluation quality when labelled ground truth exists, instead of presenting an unexplained vulnerability count.

## Operating Context

The application is an authenticated local web console backed by a FastAPI service and repository scanner. Operators enter an absolute local repository path, monitor scan progress, inspect assets and evidence, export risk and CBOM data, and compare results with repository-provided ground truth when available.

## Capabilities and Constraints

- Preserve role-based write restrictions and existing API contracts.
- Support Windows and Linux absolute repository paths.
- Risk levels are Critical, High, Medium, and Low, but the interface must clearly say when a scan contains only Medium and Low findings.
- A Medium/Low-only result must not be interpreted as proof that a repository is safe; risk depends on usage, data lifetime, exposure, and migration context.
- Precision, recall, and F1 are shown only when a valid ground-truth evaluation exists. Missing evaluation data must be labelled unavailable, never replaced with a fabricated score.
- The web interface must remain keyboard accessible, responsive, and usable at desktop and mobile widths.

## Brand Commitments

Keep the ECDAT name, the existing logo asset, and the phrase “evidence-backed cryptographic discovery assurance.” The product voice is direct, technical, and calm.

## Evidence on Hand

- Existing API responses, scan events, asset evidence, risk reports, and CycloneDX CBOM data.
- A bundled controlled `test-repo/ground_truth.json` evaluation corpus.
- No customer claims, production benchmarks, or universal accuracy claim may be fabricated.

## Product Principles

1. Put scanning and current scan status within immediate reach.
2. Explain risk distribution in plain language before showing dense evidence.
3. Keep evidence, confidence, and evaluation provenance visible.
4. Prefer repository-relative context over repeated machine-specific paths.
5. Never turn missing data into a positive assurance claim.
