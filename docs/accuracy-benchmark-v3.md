# External accuracy benchmark v3

Date: 2026-09-06

## Scope and review

V3 is a repository-independent Java digest holdout selected from seven complete
files in the official Bouncy Castle repository at commit
`acd2178417ebc6be9df4a8b2582fc8cd2a041f9a`. It contains eight direct SHA-1,
SHA-256, or SHA-512 call-site labels and three negative files. HMAC construction,
provider registration, constants, runtime-selected digests, SHA-1-INTERLEAVE,
SHA-512/t variants, and SHAKE are outside its declared taxonomy.

Before the first scanner run, an independent read-only reviewer verified the pinned
revision and hashes, checked every positive label against the source, and confirmed
the negative files under the declared scope. The manifest was frozen before the
scanner saw the files.

## Before and after

The scoped pre-fix scanner result was reconstructed using the previous Java rules;
the final result was run three times and was deterministic.

| Metric | Pre-fix | Post-fix |
| --- | ---: | ---: |
| Expected operations | 8 | 8 |
| True positives | 6 | 8 |
| False positives | 51 | 0 |
| False negatives | 2 | 0 |
| Precision | 10.53% | 100% |
| Recall | 75.00% | 100% |
| F1 | 18.46% | 100% |
| Clean negative files | 0 of 3 | 3 of 3 |

The two misses were direct SHA-1 digest constructions. The false positives came
from broad lexical Java hash rules matching constants, identifiers, nested HMAC
digest arguments, and excluded digest variants. The fix gives Java hash families
operation-shaped patterns and separates SHA-1, SHA-256, and SHA-512 selectors.

The first raw diagnostic included findings for algorithms outside the manifest's
SHA-only taxonomy. The evaluator now filters findings through a required manifest
algorithm allowlist and rejects labels outside that allowlist. The table reports the
reconstructed pre-fix result using that same scoped evaluator, so both columns use
the same denominator and taxonomy.

## Interpretation

The initial TP=6, FP=51 and FN=2 result is the only untouched generalization evidence
from this independently frozen selection. The defects it exposed were then used to
change the scanner, so the 100% post-fix result is regression evidence on a consumed
holdout. It does not establish general ECDAT accuracy: v3 covers one language, one
repository, three digest families, no known key sizes, and only eight positive
operations. Key-size accuracy is unavailable. Broader evidence still requires a
new frozen corpus across languages, crypto categories, libraries, aliases, and
positive key-size labels.
