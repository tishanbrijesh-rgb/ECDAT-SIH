# Five-step verification — 2026-09-06

> Historical snapshot. The current verification is [verification-2026-09-10.md](verification-2026-09-10.md).

Scope: ECDAT-SIH only. No Loop Engineering changes or deployment.
The user approved isolated workers, per-process admission, limits and cancellation.
Graphify provided navigation context; current source and executed checks were the
authority because the existing graph refers to older project paths.

## Status

| Step | Result | Remaining gate |
| --- | --- | --- |
| 1. External benchmark | V1/v2 regressions plus independently pre-reviewed Bouncy Castle v3 holdout: 7 files, 8 labels and 3 negatives | Broader holdout across supported languages and crypto categories |
| 2. Precision/recall and metadata | V2 operation metrics repeated three times identically; joint metadata scoring added | External positive key-size labels are absent |
| 3. Detection defects | Dynamic HMAC misses, Java digest declaration/constant false positives, SHA-1 and selector misses, Apache wrapper misses and nested-hash usage labels corrected | Broad lexical rules remain heuristic; this is not exhaustive detection validation |
| 4. Scan execution safety | Isolated child, admission lock, timeout, bounded reads, file-count limit and API/UI cancellation | OS sandboxing, distributed admission and crash recovery remain production work |
| 5. Docker/PostgreSQL | Three real disposable rounds pass, including authentication, scanning, PostgreSQL connectivity, backend restart persistence, dashboard delivery and cleanup | Migration upgrade/rollback, backup/restore and production TLS remain separate gates |

## Accuracy evidence

The independently reviewed v2 baseline contains 45 hash call-site labels across
eight complete files, including five negative files. Three identical runs produced
TP=29, FP=19 and FN=16: precision=60.42%, recall=64.44% and F1=62.37%. All five
negative files were clean. The baseline exposed 14 missed Java SHA-1 wrappers, two
missed underscore-form selectors, seven constant-reference false positives and 12
SHA-512 variant misclassifications. No scanner rules were changed before recording
this baseline. See [v2 benchmark report](accuracy-benchmark-v2.md).

V2 is limited to selected hash-family files from the same two repositories used by
v1. It does not establish general scanner accuracy, and it has no positive known-key
size labels. It is now a consumed holdout; scanner fixes require a new untouched
holdout for post-fix generalization evidence.

The new v3 holdout was frozen and independently reviewed before its first scan. On
seven complete Bouncy Castle files it improved from the scoped pre-fix result of
TP=6, FP=51 and FN=2 (precision 10.53%, recall 75.00%, F1 18.46%) to TP=8, FP=0 and
FN=0 in three identical runs. All three negative files are clean. V3 is now consumed
and remains narrow: Java only, one repository, three digest families, eight positive
operations and no known key sizes. See [v3 benchmark report](accuracy-benchmark-v3.md).

On the 15-operation combined external sample, before changes: TP=9, FP=8, FN=6,
precision=52.94%, recall=60%. After changes: TP=15, FP=0, FN=0, precision/recall=100%.
Each baseline and final result was repeated three times identically. Python alone
has 3 labels; Java has 12. Combined usage correctness is 15/15. All key sizes are
unknown, so external known-key-size accuracy is **unavailable**.

See [benchmark protocol](../benchmarks/README.md). These files were used to fix
the scanner and cannot now serve as independent proof of generalization. Existing
demo evaluation counts component/algorithm pairs, not precise operation identity.
Lexical rules can still match identifier/import names that are not executed calls;
general precision must not be inferred from the selected digest benchmark.
Java rule collection is line-based, so calls split across physical lines can be
missed. Replacing it with multiline statement parsing or a Java parser is a broader
scanner change and remains future work.

The controlled demo now produces 69 evidence records and 61 correlated findings.
The reduction from 72/64 removes three Java digest declarations/import matches.
ECDSA nested hash arguments no longer override signature usage; AES method names
containing digest/verify no longer override encryption usage.

## Repeated local checks

- Final suite: 88 tests pass; one symlink creation test
  skipped because Windows does not permit it. Three final rounds with
  `ResourceWarning` promoted to errors.
- Tests cover real subprocess success, timeout, cancellation, launch failure,
  simultaneous admission, invalid limits, database-submission failure, cancellation
  authorization and late-cancellation/completion races, plus discovery regressions.
- Earlier browser checks cancelled three `C:\Python314` scans successfully and
  completed a subsequent `/test-repo` scan. The final automated API integration
  validates the current 61-finding inventory. Disposable SQLite and credentials
  were used; existing scan data was not rewritten.
- Frontend production build: three rounds passed. Formatting, Python compilation,
  dependency consistency and whitespace checks passed.
- A network-enabled `npm audit --omit=dev` completed with zero reported
  vulnerabilities.

## Worker operating contract

Run **one Uvicorn process / one application instance**. The admission lock belongs
to a server process, not PostgreSQL; multiple workers/replicas would each admit a
scan and cancellation might reach the wrong process.

| Variable | Default | Accepted maximum |
| --- | --- | --- |
| `ECDAT_SCAN_TIMEOUT_SECONDS` | 300 seconds | 3600 seconds |
| `ECDAT_MAX_FILE_BYTES` | 8388608 (8 MiB) | 134217728 (128 MiB) |
| `ECDAT_MAX_SCAN_FILES` | 100000 enumerated files | 1000000 |

All limits must be positive integers. Invalid configuration fails closed with 503;
a second active scan receives 409. Oversized/linked supported files reduce coverage
instead of silently counting as processed. Linked directories are excluded and
reported as a blind spot. The worker never intentionally executes scanned code.

`POST /api/scans/{id}/cancel` requires an administrator/security analyst and returns
202 for an accepted request. Poll until `cancelled`, `timed_out`, `failed`, or
`completed`; cancellation is best-effort and must not overwrite completed results.
History can reattach to an active scan after returning to the page.

Subprocess separation is **not a security sandbox or a hard memory quota**. The
child inherits server permissions and environment. Read-size and file-count limits
do not cap all Python/parser allocations. Parent crashes, host shutdown, stale jobs,
filesystem mutation races and hostile parsers need further hardening. Restrict scan
roots and use least-privilege accounts; do not expose this prototype to untrusted
repositories as a production security boundary.

## Deployment verification

Removed the insecure fallback PostgreSQL password from the backend image and added
`.dockerignore` exclusions for local secrets, databases, clones and build artifacts.
No third-party Python dependencies were added. `req.txt` now documents that the
benchmark and Compose verification scripts use only the Python standard library.

With Docker Compose 2.24.4+ installed and ports 18080/18081 available, run:

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_compose
```

This builds a uniquely named disposable Compose project with random credentials,
checks readiness/authentication/scans/reports/frontend/PostgreSQL, restarts the
backend and verifies persistence in three rounds. Its final cleanup removes only
that verification project's containers and volume. It does not migrate or delete
the regular project's database. On 2026-09-06 all three real Docker/PostgreSQL
rounds passed after the backend and dashboard production images were hardened.
TLS/reverse proxy, backup/restore, OS isolation and multi-instance coordination are
separate release gates. Database migration testing is the next planned phase.
