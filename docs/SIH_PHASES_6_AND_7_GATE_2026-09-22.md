# SIH Phases 6–7 Gate Evidence

**Date:** September 22, 2026  
**Target:** reproducible SIH prototype demonstration

## Phase 6 — Judge-facing interface

- Added a keyboard-accessible four-step demo path on the assurance dashboard: start scan, verify history, inspect findings, export CBOM.
- The path retains the selected scan ID for inventory and CBOM deep links.
- Metric language consistently separates supported-file coverage, evidence confidence and evaluation-corpus accuracy.
- Existing responsive/browser coverage exercises 375, 390, 768, 1024, 1280 and 1440 pixel viewports, reduced motion, keyboard navigation and horizontal overflow.
- Long inventories remain server-paginated instead of rendering thousands of DOM rows.

## Phase 7 — Deployment packaging

- `scripts/start_sih.ps1` provides the Windows launch path.
- First launch generates a private gitignored `.env.sih` with random database password, token secret and demo administrator password.
- Compose validates configuration, runs Alembic migrations, waits for PostgreSQL/backend/dashboard health and preserves history in the `pgdata` volume.
- PostgreSQL and backend bases are digest-pinned; dashboard bases use explicit major/runtime families and remain a packaging limitation until their digests are frozen. Application services run without root privileges. Backend and dashboard use read-only filesystems, dropped capabilities, no-new-privileges, finite memory/CPU/PID limits and loopback-only published ports.
- Repository input is mounted read-only and limited to `/test-repo` in the containerized SIH path.
- Recovery and non-destructive shutdown commands are documented in `README.md`.

## Host limitation

Docker is not installed on this workstation, so container creation and the three-round PostgreSQL persistence smoke test remain **blocked**, not passed. Static deployment-contract tests, PowerShell parsing and the native application suites can still be verified here. Run `python scripts/verify_compose.py` after Docker Desktop is installed to close this evidence gap.
