# Discovery accuracy audit — 2026-09-04

> Historical audit. Current regression evidence is summarized in [verification-2026-09-10.md](verification-2026-09-10.md).

Scope: local ECDAT-SIH collector, correlation, confidence and evaluation review.
This is a targeted audit, not a certification or an exhaustive security review.

This document records the initial audit. Subsequent operation-correlation and
verification work resolves several findings below; see
[verification-2026-09-04.md](verification-2026-09-04.md) for the current status.

## Fixed locally

- Confidence counted duplicate source names as independent agreement. Deduplicate
  before averaging and applying the bonus. The correlator already deduplicated its
  source list, so this is defensive correctness for other callers.
- Maven parsing paired unrelated groupId/artifactId tags by position, including
  parent/project coordinates. Parse direct project dependencies structurally.
- Maven comments/plugins and lookalike group names produced false positives.
  Ignore non-dependency nodes and require exact known group names.
- Python requirement names with comments, environment markers, normalized spelling
  or python-jose extras were missed. Normalize the declared package name.
  Markers are preserved in raw evidence, not evaluated against the scanning host.

Eight new test methods in test_discovery_regressions.py cover these cases.
Before fixes: nine failing assertions including subtests. After fixes: all 19
tests pass, including the existing end-to-end test and earlier SHA-1 regressions.

## Open high-priority findings

Update: operation-v2 now addresses item 1's over-merging and order dependence.
See operation-correlation.md for behavior, new counts and remaining limitations.

1. Correlation merges distinct operations by component and algorithm. Two RSA
   records with signing/encryption usage produce one finding; reversing input
   changes the selected usage. This affects migration guidance and logical IDs.
2. AST matches algorithm words in arbitrary string arguments: a print call with
   the text `sha256 is a word, not a crypto call` produces SHA-256 evidence.
   Import presence also does not establish execution or algorithm use.
3. Regex comment removal is not string-aware. A Java line beginning with a URL
   literal containing `https://` is truncated before a later Cipher call.
4. Dependency mappings describe library capabilities, not observed algorithm use.
   Correlation also discards some dependency records based on other algorithms
   found in the component, which is not evidence that the capability is absent.
5. Coverage measures inventory readability, not collector success. AST syntax
   errors and malformed certificates are not incorporated into failed-file counts.
   Zero supported files currently reports 100 percent.
6. Collector scopes disagree: inventory/rules exclude several generated/vendor
   directories while AST/dependency/certificate walkers do not. Certificate
   collector includes .cer but inventory does not. Symlink boundary handling also
   needs a unified policy and tests before untrusted repositories are accepted.
7. Evaluation compares component/algorithm pairs only. It cannot detect wrong
   usage, provenance, key size or over-merging. Per-source metrics use correlated
   output rather than independently evaluated collector output.
8. Certificate key type is treated as usage (RSA as encryption, EC as ECDSA),
   although key type alone does not establish the protocol operation.

Items 1–3 were demonstrated with in-memory adversarial inputs. Items 4–8 are
confirmed implementation limitations from source inspection; coverage isolation
was also checked with mocked collector output, not a real unreadable-file test.

## Next change requiring design approval

Separate evidence of declared capabilities/imports from observed static operations;
correlate by explicit operation context; retain unknown/ambiguous context rather
than selecting the first value. Propagate per-collector success/failure and scope
through metrics. Update API/dashboard/exports and ground truth together so changed
counts are explained, not adjusted merely to retain the demo score.

Do not claim real-world accuracy from the controlled demonstration corpus.
No dependencies installed, no Loop configuration changed, and no publication made.

## Dependency parser limitations after this patch

Only direct project dependencies are read from Maven XML. Profiles, dependency
management, inherited coordinates, property resolution and transitive dependencies
remain unsupported. Requirements parsing is declared-name extraction, not full
pip resolution; include files and environment applicability remain unsupported.
Library-to-algorithm mappings remain heuristic. XML DTD/entity declarations are
rejected; parser resource limits and overall scan isolation remain separate work.
