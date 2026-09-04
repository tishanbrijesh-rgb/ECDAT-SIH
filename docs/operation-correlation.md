# Operation-aware correlation (operation-v2)

New scans group evidence by component, algorithm, explicit usage, normalized file
location and operation anchor. Distinct operations and usages no longer collapse
into one component/algorithm finding. Unknown or unsupported usage remains unknown;
algorithm category does not establish a protocol operation.

Anchors use explicit operation_id first, then source line, then a deterministic
hash of unlocated evidence details. Matching evidence combines only when all group
keys match. This deliberately avoids assuming an import, dependency or certificate
supports a particular call. Collector aliases and cross-source operation matching
still need future work; conservative splitting may produce duplicate observations.

IDs hash a versioned tuple, excluding random evidence UUIDs. They are deterministic
for unchanged file paths and anchors and independent of input order. They are not
stable across checkout relocation, moved lines or changed collector anchors.

Conflicting key sizes, libraries or protocols are retained in context_conflicts;
the single-valued field becomes null/empty rather than choosing the first record.
Algorithm disagreement on explicit operation IDs is scoped to the file. Conflict
detection remains heuristic and does not establish whether alternate algorithms
are legitimate; review evidence before treating a flag as an actual defect.

Operation context is persisted in existing evidence_json, exposed in assets/CBOM,
and included with usage in risk reports and evidence-graph nodes. No database
migration or historical scan rewrite is performed. Historical IDs remain as-is.
Unknown RSA usage now receives assessment guidance rather than an ML-KEM guess.

## Demo and evaluation impact

The existing 78 raw records produce 70 retained groups, including unknown-usage
observations, across the same 15 component/algorithm pairs. The existing dependency
filter still removes eight records; this patch does not validate that heuristic.
There are 29 groups carrying modeled quantum-vulnerable algorithms and two conflict
flags. These counts are not counts of unique confirmed runtime operations.

Ground truth has not been altered to force a passing score. The legacy evaluator
is explicitly labeled component_algorithm granularity and warns that its scores do
not validate operation identity or usage. Dedicated mixed-operation unit/API tests
cover splitting, metadata conflict, order invariance, IDs, and persisted guidance.

Still outstanding: capability-vs-use classification, collector false positives,
accurate parsing coverage, operation-level ground truth, and confidence calibration.
