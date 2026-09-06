# ECDAT working memory

Updated: 2026-09-06

## Repository state

- Remote: `https://github.com/tishanbrijesh-rgb/ECDAT-SIH.git`
- Active branch: `fix/sha1-recommendation`
- Latest verified implementation commit before this memory update: `d137939`
  (`Harden production container images`).
- Frontend improvements are intentional project work. Do not revert or overwrite
  them while changing backend, scanner, deployment or database code.
- Phases 1 and 2 are complete. Phase 3 has not started and requires the user's
  explicit approval.

## Verified baseline

- Backend: 88 tests pass; one Windows symlink test skips when symlinks are
  unavailable.
- Frontend: 7 unit tests, 2 Edge E2E tests, formatting, TypeScript and production
  build pass.
- Security: pip-audit and npm audit are clean; Bandit has no medium/high findings;
  no tracked secret signatures or large files were found.
- Docker/PostgreSQL: disposable verifier passes 3/3 rounds, including persistence
  after backend restart and cleanup.
- Dashboard container: Node 22 build stage, unprivileged nginx runtime, explicit
  health check, about 26 MB.
- Backend container: unprivileged UID/GID 10001, no compiler toolchain, about 77 MB.

## Operational constraints

- Never commit `.env`, credentials, token secrets, database files, virtual
  environments, `node_modules`, build output or Graphify output.
- Use random temporary credentials for verification and let
  `scripts.verify_compose` clean up its uniquely named Compose project.
- Keep one Uvicorn process until scan admission and cancellation are coordinated
  across processes.
- Treat subprocess isolation as reliability containment, not a complete security
  sandbox.
- Accuracy claims must name the evaluated corpus. The v2 and v3 corpora are consumed
  regression evidence and cannot be reused as new independent holdouts.

## Next authorized boundary

Before Phase 3, the repository and release gate are clean. After user approval,
Phase 3 should add a migration framework, establish a baseline migration for the
current SQLAlchemy schema, test upgrades on a populated PostgreSQL volume, document
rollback/recovery behavior, and stop using implicit table creation as the production
schema-management strategy.

