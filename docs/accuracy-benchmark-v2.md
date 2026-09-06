# External accuracy benchmark v2

Date: 2026-09-06

## Scope

The v2 benchmark freezes eight complete files from two pinned external repository
checkouts before its first scanner run. It contains 45 positive hash call-site
labels across three Java files and five negative Python/Java files. It covers MD5,
SHA-1, SHA-256 and SHA-512 under the scope declared in
`benchmarks/external-v2.json`.

An independent read-only reviewer checked every positive label, every negative
file, each file checksum and both repository revisions. The reviewer found all 45
labels correct and exhaustive under the declared scope, and all five negative files
correctly negative. The selected files had not previously been scanned for this
benchmark, but they come from the same two repositories and Apache digest package
family used by v1. Results therefore describe this selected-file hash benchmark,
not general ECDAT scanner accuracy.

## Baseline result

Three identical runs produced the same combined result:

| Metric | Result |
| --- | ---: |
| Expected operations | 45 |
| True positives | 29 |
| False positives | 19 |
| False negatives | 16 |
| Precision | 60.42% |
| Recall | 64.44% |
| F1 | 62.37% |
| Clean negative files | 5 of 5 |

No positive known-key-size labels exist in v2, so key-size accuracy is unavailable.
All positive labels are hashing operations, so this benchmark does not establish
accuracy for encryption, signatures, key establishment, TLS, certificates,
dependencies or the six other supported source languages.

## Exposed scanner issues

- Fourteen Java SHA-1 wrapper calls are missed because the rule set has no SHA-1
  algorithm entry.
- Two Java calls using `SHA_256` and `SHA_512` selector constants are missed.
- Seven salt-prefix or algorithm-constant references are reported as operations.
- Twelve SHA-512/224 and SHA-512/256 operations outside this benchmark taxonomy are
  incorrectly reported as SHA-512.

These issues require changes to shared Java detection behavior. They were not fixed
during the baseline so the reviewed score remains an honest measurement of the
pre-fix scanner.

## Evaluator verification

The evaluator now validates manifests before filesystem access, confines sources to
the repository and declared checkout, rejects unsafe or duplicate names, verifies
pinned Git revisions and SHA-256 hashes, stages the exact bytes that were hashed,
preserves unique relative paths, and uses a single one-to-one metadata assignment.
It reports undefined metrics as unavailable for empty negative-only samples.

The focused evaluator suite and the full ECDAT suite passed after these changes.
V1 remains a regression corpus at TP=15, FP=0 and FN=0. V2 is now a consumed
holdout; future scanner fixes must preserve this baseline and use a new untouched
holdout for post-fix generalization claims.

## Post-fix regression result

After the independently reviewed baseline was recorded, the Java rules were changed
to match digest constructions and named calls rather than bare identifiers. Three
identical post-fix runs produced TP=45, FP=0 and FN=0. This is a regression result on
a consumed holdout, not independent evidence of generalization. The separately
frozen Bouncy Castle v3 holdout provides that narrower independent check; see
[v3 benchmark report](accuracy-benchmark-v3.md).
