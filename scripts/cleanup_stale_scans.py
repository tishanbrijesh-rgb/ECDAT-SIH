"""Stale scan-job cleanup script — CLI wrapper around the recovery service.

Delegates to backend.services.stale_job_recovery for consistent behaviour
with the app-lifespan recovery path.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure backend package is importable when running as a standalone script.
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.services.stale_job_recovery import recover_stale_jobs, utc_now


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Mark stale scan jobs (running/queued > 3h) as failed.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report stale jobs without modifying the database.",
    )
    args = parser.parse_args()

    cleaned = recover_stale_jobs(dry_run=args.dry_run)
    print(f"Stale-job cleanup complete. Jobs cleaned up: {cleaned}")


if __name__ == "__main__":
    main()
