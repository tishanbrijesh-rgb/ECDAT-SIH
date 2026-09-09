"""Stale scan-job cleanup script.

Queries the database for scan jobs stuck in 'running' or 'queued' status
for more than 3 hours, marks them as failed, and appends a blind_spot note.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select, update

# Ensure backend package is importable when running as a standalone script.
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.db import SessionLocal
from backend.models.scan_job import ScanJobDB


STALE_THRESHOLD = timedelta(hours=3)
STALE_STATUSES = ("running", "queued")


def utc_now() -> datetime:
    """Return naive UTC for compatibility with SQLite DateTime values."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def find_stale_jobs(db_session) -> list[ScanJobDB]:
    """Return jobs in STALE_STATUSES older than STALE_THRESHOLD."""
    cutoff = utc_now() - STALE_THRESHOLD
    stmt = (
        select(ScanJobDB)
        .where(ScanJobDB.status.in_(STALE_STATUSES))
        .where(ScanJobDB.started_at < cutoff)
        .order_by(ScanJobDB.started_at.asc())
    )
    return list(db_session.scalars(stmt).all())


def mark_job_failed(db_session, job: ScanJobDB, now: datetime) -> None:
    """Update a single stale job to failed status with a blind_spot note."""
    hours_running = (now - job.started_at).total_seconds() / 3600
    note = f"Marked failed by stale-job cleanup (running for {hours_running:.1f} hours)"

    # Append to blind_spots JSON array safely.
    blind_spots = list(job.blind_spots or [])
    blind_spots.append({"note": note, "cleaned_at": now.isoformat()})

    db_session.execute(
        update(ScanJobDB)
        .where(ScanJobDB.id == job.id)
        .values(
            status="failed",
            finished_at=now,
            blind_spots=blind_spots,
        )
    )


def run_cleanup(dry_run: bool = False) -> int:
    """Run the stale-job cleanup. Returns the number of jobs cleaned up."""
    db = SessionLocal()
    try:
        stale_jobs = find_stale_jobs(db)
        now = utc_now()

        if dry_run:
            for job in stale_jobs:
                hours_running = (now - job.started_at).total_seconds() / 3600
                print(
                    f"[dry-run] job_id={job.id} status={job.status} "
                    f"started_at={job.started_at.isoformat()} age={hours_running:.1f}h"
                )
            return len(stale_jobs)

        for job in stale_jobs:
            mark_job_failed(db, job, now)

        db.commit()

        for job in stale_jobs:
            hours_running = (now - job.started_at).total_seconds() / 3600
            print(
                f"cleaned job_id={job.id} status={job.status} "
                f"started_at={job.started_at.isoformat()} age={hours_running:.1f}h"
            )

        return len(stale_jobs)
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Mark stale scan jobs (running/queued > 3h) as failed."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report stale jobs without modifying the database.",
    )
    args = parser.parse_args()

    cleaned = run_cleanup(dry_run=args.dry_run)
    print(f"Stale-job cleanup complete. Jobs cleaned up: {cleaned}")


if __name__ == "__main__":
    main()
