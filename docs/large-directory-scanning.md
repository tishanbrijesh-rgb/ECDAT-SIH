# Large-directory scanning

The local Windows backend can scan `C:\Python314`. The backend process must be
able to read that directory, and `ECDAT_ALLOWED_SCAN_ROOTS`, when configured,
must permit it. A host Windows path is not a path inside a Docker container:
the supplied Compose configuration exposes `/test-repo` only. Additional mounts
and allowlisted roots require a deliberate deployment configuration change.

The scanner inventories the tree once, then routes each supported file through
the applicable collectors. All collectors now follow the inventory's existing
exclusions: `.git`, `node_modules`, `dist`, `build`, and `__pycache__`.
`site-packages` is not excluded. Certificate inventory includes `.cer` as well
as `.crt` and `.pem`.

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

## Limits

- Inventory and an individual slow file can still delay progress updates.
- Coverage counts supported files without reported collector read/parser errors.
  A partially parsed certificate bundle or a Python AST failure reduces coverage,
  even when other evidence from the file remains available. This still does not
  measure detection completeness or validate every language's syntax.
- Compiled binaries are not analyzed. Large evidence sets remain in memory.
- This is an in-process background worker, not a durable job queue. Process
  termination, database outages, hard timeouts, cancellation and restart
  recovery need separate production hardening.

## Verification

Regression tests cover unchanged demo evidence counts, progress persistence,
empty directories, shared exclusions, inclusion of `site-packages` and `.cer`,
and failed-job finalization for scanner, correlator and risk-scoring exceptions.
