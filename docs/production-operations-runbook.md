# ECDAT Production Operations Runbook

## Release gate

Run `python scripts/verify_compose.py` from a clean checkout. It creates a
randomly named disposable Compose project, applies every migration to
PostgreSQL, performs three authenticated scans, checks outputs, restarts the
API, verifies persistence, and destroys only that disposable project.

## PostgreSQL backup and restore

Create an encrypted, access-controlled backup outside the application host:

```sh
docker compose exec -T db pg_dump -U ecdat -d ecdat --format=custom > ecdat.dump
```

Restore only into an empty recovery database, then run `alembic upgrade head`
and `/ready` before switching traffic:

```sh
createdb ecdat_recovery
pg_restore --exit-on-error --clean --if-exists -d ecdat_recovery ecdat.dump
DATABASE_URL=postgresql://.../ecdat_recovery alembic upgrade head
```

Quarterly restore drills must record backup checksum, restore duration,
row-count comparisons for every application table, migration revision, and the
operator identity. Never validate recovery by overwriting the live database.

## Secret rotation

Generate a new database password and token secret in the secret manager,
deploy database credentials first, restart API replicas, then revoke old token
sessions. Existing bearer tokens intentionally become invalid after signing-key
rotation. Verify anonymous requests remain `401` and `/ready` remains healthy.

## Bad-release rollback

Stop traffic, retain a database backup, deploy the previous image digests, and
downgrade Alembic only when the target migration explicitly supports downgrade.
Never use `git reset --hard` or delete the production volume. Run `/ready`, an
authenticated inventory query, and a controlled scan before restoring traffic.

## Stuck leases and corrupted exports

Use `scripts/cleanup_stale_scans.py` for expired leases; do not mutate lease rows
manually. Preserve logs and audit events. A corrupt or oversized export must be
quarantined, regenerated from immutable scan rows, checksum-verified, and never
served partially.

## Service-level indicators

Alert on API 5xx rate, p95 request latency, oldest queued dispatch age, scan
completion/failure ratio, active worker and lease saturation, SSE disconnect
rate, and export failure ratio. Initial objectives are: API success >=99.5%,
95% of admitted scans start within 60 seconds, >=99% of bounded exports succeed,
and no expired lease remains unreclaimed for more than two lease periods.

## Load and soak proof

CI runs performance, large-output, SSE, evaluation-limit, and lifecycle suites.
Before a public pilot, run the disposable Compose rehearsal plus a two-hour soak
at expected peak concurrency and attach CPU, memory, queue-age, completion, and
error-rate graphs to the release record.
