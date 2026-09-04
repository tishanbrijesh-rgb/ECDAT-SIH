# Detection and correlation regressions — 2026-09-04

This follow-up supersedes the demo counts in the earlier verification report.
It does not establish real-world detection accuracy or production readiness.

## Corrections

- Python hash calls are resolved through imports and aliases, with conservative
  handling of reassignment, parameters, local bindings and comprehension scopes.
  Arbitrary `padding()` calls and objects merely named `hashlib` are not crypto.
- Hash selectors use exact normalized names, accepting `SHA256` and `SHA-256`
  without matching longer arbitrary strings. HMAC digest arguments and supported
  cryptography hash constructors remain discoverable.
- Python hash findings use the AST collector only. Regex name hits are neither
  independent evidence nor additional operations. This intentionally changes
  source counts and confidence rather than manufacturing agreement.
- Call line/column identity preserves distinct same-line calls. Correlation's
  location fallback also includes columns when supplied. Rule statements on the
  same line have separate identities and do not share key-size metadata.
- Quoted code examples, ordinary strings, text blocks and template strings are
  masked by the rule collector; recognized algorithm-selector literals remain.
- Key sizes come from supported algorithm-specific API arguments. AES-256 is
  recognized in `KeyGenerator.getInstance("AES").init(256)`; unrelated integers
  no longer become key sizes. Unresolved values remain unknown.
- Empty/unsupported scope reports zero coverage plus an explicit blind spot.

## Verification

- 51 tests pass, including permanent challenge fixtures, binding/scope cases,
  key-size isolation and operation identity checks.
- Frontend formatting and production build pass; frontend source unchanged.
- The same 12-case challenge corpus was run against HEAD's old collectors and
  the modified collectors: TP/FP/FN changed from 7/3/1 to 8/0/0. Precision changed
  from 70% to 100%; recall from 87.5% to 100%, on these fixtures only.
- Original eight regression fixtures still produce TP=4, FP=0, FN=0.
- Controlled demo: 72 evidence records and 64 findings, down from 78/70.
  Ten lexical Python hash records were removed and four structural records added
  (three hash constructors and one HMAC digest argument). All 15 expected
  component/algorithm pairs remain: precision/recall/F1 are 100% at that granularity.

## Remaining limits

This is not full Python name/data-flow analysis or multi-language semantic
analysis. Dynamic imports, complex control flow, import resolution against local
lookalike modules, and general cross-statement key-size propagation are not
resolved. Non-Python rule detection remains heuristic. Dependency/import evidence
is not proof of runtime use. Demo evaluation does not validate operation identity,
key sizes or usage; dedicated regression assertions cover the reported defects.

New call/statement anchors change some logical IDs. Rescan to obtain corrected
findings; persisted historical scans are not rewritten by this patch.
