# Large-directory scanning

The local Windows backend can scan `C:\Python314`. The backend process must be
able to read that directory, and `ECDAT_ALLOWED_SCAN_ROOTS`, when configured,
must permit it. A host Windows path is not a path inside a Docker container:
the supplied Compose configuration exposes `/test-repo` only. Additional mounts
and allowlisted roots require a deliberate deployment configuration change.

The scanner inventories the tree once, then routes each supported file through
the applicable collectors. All collectors now follow the inventory's existing
exclusions: `.git`, `node_modules`, `dist`, `build`, `__pycache__`, generated
tool caches, and `.runtime`. The default `source` profile also excludes `.venv`,
`venv`, and `env`; set `ECDAT_SCAN_PROFILE=environment` when installed
environment contents such as `site-packages` are intentionally in scope.
Certificate inventory includes `.cer` as well as `.crt` and `.pem`.

While a scan is running, `collector_stats` includes `_files_processed` and
`_files_total`. Updates are emitted between files about once per second, with
initial and final counts. These fields represent collection progress, not
completion of correlation or storage. Completed jobs replace these temporary
fields with the final collector evidence counts. The dashboard shows both
collection progress and the subsequent correlation/storage phase.

Exceptions in collection, correlation, scoring or persistence mark the job
failed and set its finish time, provided the database is still writable.
Failure descriptions expose the exception class, not its potentially sensitive
message. Asset persistence remains one transaction.

Completed scan list/detail responses also expose `failures` as a safe relative
path plus a fixed category: `unreadable`, `oversized`, `linked_file`,
`parse_error` or `certificate_error`. Absolute paths, traversal paths and raw
parser messages are rejected. The Scan Detail page presents these records.

Certificate deprecation warnings are treated as controlled certificate errors
now, before the `cryptography` library turns them into hard failures. Other PEM
blocks continue to be evaluated.

## Limits

- Inventory and an individual slow file can still delay progress updates.
- Coverage counts supported files without reported collector read/parser errors.
  A partially parsed certificate bundle or a Python AST failure reduces coverage,
  even when other evidence from the file remains available. This still does not
  measure detection completeness or validate every language's syntax.
- Compiled binaries are not analyzed. Evidence remains in memory, but
  `ECDAT_MAX_EVIDENCE` bounds the aggregate retained records (100,000 by default).
- This uses an in-process supervisor and child worker, not a durable job queue. Process
  termination, database outages, hard timeouts, cancellation and restart
  recovery need separate production hardening.

## Verification

Regression tests cover unchanged demo evidence counts, progress persistence,
empty directories, shared exclusions, inclusion of `site-packages` and `.cer`,
failed-job finalization, sanitized per-file failures, and mixed certificate
bundles. The latest `C:\Python314` result is recorded in
`stages-1-4-verification-2026-09-07.md`.
