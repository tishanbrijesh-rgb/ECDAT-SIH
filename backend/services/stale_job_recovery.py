"""Stale scan-job recovery — marks long-running/queued jobs as failed."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update

from backend.db import SessionLocal
from backend.logging_config import get_logger
from backend.models.scan_job import ScanJobDB

logger = get_logger("ecdat.recovery")

STALE_THRESHOLD = timedelta(hours=3)
STALE_STATUSES = ("running", "queued")


def utc_now() -> datetime:
    """Naive UTC for SQLite DateTime compatibility."""
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


def recover_stale_jobs(dry_run: bool = False) -> int:
    """Find stale jobs and mark them failed. Returns count recovered."""
    db = SessionLocal()
    try:
        stale = find_stale_jobs(db)
        now = utc_now()

        if not stale:
            return 0

        if dry_run:
            for job in stale:
                age = (now - job.started_at).total_seconds() / 3600
                logger.info(
                    "Stale job found (dry-run)",
                    extra={"extra_data": {"job_id": job.id, "status": job.status, "age_hours": round(age, 1)}},
                )
            return len(stale)

        for job in stale:
            age = (now - job.started_at).total_seconds() / 3600
            blind = list(job.blind_spots or [])
            blind.append(
                {
                    "note": "Recovered from stale state by app lifecycle cleanup",
                    "age_hours": round(age, 1),
                    "recovered_at": now.isoformat(),
                }
            )
            db.execute(
                update(ScanJobDB)
                .where(ScanJobDB.id == job.id)
                .values(
                    status="failed",
                    finished_at=now,
                    blind_spots=blind,
                )
            )
            logger.info(
                "Recovered stale job",
                extra={"extra_data": {"job_id": job.id, "status": job.status, "age_hours": round(age, 1)}},
            )
        db.commit()
        return len(stale)
    finally:
        db.close()
