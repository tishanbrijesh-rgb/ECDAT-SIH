# Verification — 2026-09-04

Scope: ECDAT-SIH only, including the updated frontend. Loop Engineering was not
modified. This is a targeted local verification, not production certification.

## Verified

- Python 3.14 isolated environment installed successfully from `req.txt`.
- 42 unit/API/regression tests pass with ResourceWarning promoted to errors.
- Compilation, dependency consistency, frontend formatting and production build pass.
- Browser login and controlled scan complete: 78 evidence records, 70 correlated
  findings. Authorization, exports, validation and failed-job behavior are also
  exercised by the API integration suite.
- The latest browser run of `C:\Python314` completed with 1,935 evidence records,
  1,934 findings and 99.61% processing coverage across 2,314 supported files.
  Live progress and automatic navigation to the completed inventory worked.
  This is a functional check, not a throughput guarantee or accuracy benchmark.
  Legacy certificate serial-number deprecation warnings were observed.
- Viewer login showed no scan controls; report actions were exercised. Full
  Docker execution was unavailable locally; Compose YAML and localhost port
  binding assertions passed, but do not substitute for deployment testing.
- Eight targeted adversarial fixtures yield TP=4, FP=0, FN=0: precision and recall
  100% on this small regression corpus only. The controlled demo evaluation uses
  component/algorithm pairs, not operation-level ground truth. Neither establishes
  real-world accuracy.
- Python dependency advisory audit reported no known vulnerabilities. An earlier
  npm audit also reported zero; the final npm recheck timed out at the registry.
  Network failures are reported as failures, never as a clean audit.

## Corrections included

- Authentication on data endpoints, role-header spoofing disabled by default,
  explicit credentials/secrets, bounded login input and safe validation responses.
- Evidence redaction and operation-aware correlation with deterministic IDs.
- Dependency parsing and duplicate-source confidence corrections.
- Arbitrary Python strings no longer count as crypto calls; comments and quoted
  URLs no longer hide later Java calls or create URL-only TLS evidence.
- Shared scan inventory and reported collector errors contribute to file coverage.
  Malformed Python/XML/certificates no longer silently claim full processing.
- Scan polling retries transient failures and prevents duplicate initial requests.
- Release checks stop on native command failure; advisory requests have a timeout.
- Latest frontend design retained, formatted, and misleading demo-account hint removed.
- Root dependency entry point and generated/local-file exclusions updated.
- Compose requires an explicit database password and publishes ports on localhost.
  Set `ECDAT_DB_PASSWORD` to a random 64-character hexadecimal value. Existing
  PostgreSQL volumes retain their old password: rotate it separately and update
  configuration; do not delete the volume to resolve an authentication failure.

The original discovery audit's items 1–3, parser-error coverage, and shared-inventory
scope were addressed. Import/dependency capability interpretation, complete language
semantics, operation-level evaluation and symlink policy remain limitations.

## Remaining before production

Independent labelled precision/recall benchmark; durable isolated scan workers,
resource/concurrency limits and cancellation; untrusted-repository boundary review;
identity-provider/password-storage improvements, rate limiting, revocation and TLS;
deployment/PostgreSQL testing. No exhaustive vulnerability-free claim is made.

The frontend loads Google Fonts with local fallbacks; offline environments should
expect fallback typography. Browser authentication is memory-only and requires
sign-in again after a full page reload.
