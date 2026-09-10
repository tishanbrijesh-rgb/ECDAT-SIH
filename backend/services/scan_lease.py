"""
Scan-lease service — DB-backed worker admission and expiry reconciliation.

Each active scan claim is a ScanLeaseDB row with a TTL.  This lets multiple
API processes run without risking duplicate admissions: a worker that crashes
or is replaced releases nothing, but the lease expires automatically.
"""
from __future__ import annotations

import os
import socket
import threading
from datetime import datetime, timedelta, timezone

from backend.logging_config import get_logger
from backend.security import record_audit

logger = get_logger("ecdat.scan_lease")

# Default lease TTL: same default as scan timeout (300 s) plus a 60 s grace period.
_LEASE_TTL = timedelta(
    seconds=int(os.getenv("ECDAT_SCAN_TIMEOUT_SECONDS", "300")) + 60
)
_LEASE_TABLE = "scan_leases"


def _worker_id() -> str:
    return f"{socket.gethostname()}-{threading.get_native_id()}"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def acquire_lease(db_session, scan_id: int) -> bool:
    """Try to claim an exclusive lease on *scan_id*.

    Returns True if the lease was acquired, False if another worker holds it
    or the job is already finished.
    """
    from backend.models.scan_lease import ScanLeaseDB
    now = _utc_now()
    # Reconcile any expired leases for this job before attempting claim.
    expired = (
        db_session.query(ScanLeaseDB)
        .filter(ScanLeaseDB.scan_job_id == scan_id, ScanLeaseDB.expires_at < now)
        .all()
    )
    for stale in expired:
        db_session.delete(stale)
    existing = (
        db_session.query(ScanLeaseDB)
        .filter(ScanLeaseDB.scan_job_id == scan_id, ScanLeaseDB.released.is_(False))
        .first()
    )
    if existing is not None:
        return False
    lease = ScanLeaseDB(
        scan_job_id=scan_id,
        worker_id=_worker_id(),
        acquired_at=now,
        expires_at=now + _LEASE_TTL,
        released=False,
    )
    db_session.add(lease)
    db_session.flush()
    try:
        record_audit("scan.lease.acquired", f"scan:{scan_id}", "system",
                     {"worker": lease.worker_id, "expires_at": lease.expires_at.isoformat()})
    except Exception:
        pass
    return True


def release_lease(db_session, scan_id: int) -> None:
    """Release the lease on *scan_id* if this worker still holds it."""
    from backend.models.scan_lease import ScanLeaseDB
    lease = (
        db_session.query(ScanLeaseDB)
        .filter(ScanLeaseDB.scan_job_id == scan_id, ScanLeaseDB.released.is_(False))
        .first()
    )
    if lease is not None:
        lease.released = True
        lease.worker_id = ""
        db_session.flush()
        try:
            record_audit("scan.lease.released", f"scan:{scan_id}", "system", {})
        except Exception:
            pass


def reconcile_expired_leases(db_session, older_than: timedelta | None = None) -> int:
    """Mark expired leases as released so jobs can be reclaimed.

    Returns the number of leases reconciled.
    """
    from backend.models.scan_lease import ScanLeaseDB
    now = _utc_now()
    expiry_cutoff = now - older_than if older_than is not None else now
    expired = (
        db_session.query(ScanLeaseDB)
        .filter(ScanLeaseDB.released.is_(False), ScanLeaseDB.expires_at < expiry_cutoff)
        .all()
    )
    count = 0
    for lease in expired:
        lease.released = True
        lease.worker_id = ""
        count += 1
        try:
            record_audit("scan.lease.expired", f"scan:{lease.scan_job_id}", "system",
                         {"acquired_at": lease.acquired_at.isoformat()})
        except Exception:
            pass
    if count > 0:
        db_session.flush()
        logger.info("Reconciled expired leases", extra={"extra_data": {"count": count}})
    return count
