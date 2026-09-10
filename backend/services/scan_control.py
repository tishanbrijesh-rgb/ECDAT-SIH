"""Single-server-process scan admission with DB-backed worker leases."""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException
from backend.logging_config import get_logger
from backend.db import SessionLocal
from backend.models.scan_job import ScanJobDB
from backend.security import record_audit
from backend.services.scan_lease import acquire_lease, release_lease
from scanner.limits import positive_int, max_file_bytes

logger = get_logger("ecdat.scan_control")


@dataclass
class Control:
    timeout: int
    scan_id: int | None = None
    cancel: threading.Event = field(default_factory=threading.Event)


_lock = threading.Lock()
_active: Control | None = None


def reserve(scan_id: int | None = None) -> Control:
    global _active
    try:
        timeout = positive_int('ECDAT_SCAN_TIMEOUT_SECONDS', 300, 3600)
        max_file_bytes()
        positive_int('ECDAT_MAX_SCAN_FILES', 100000, 1000000)
    except ValueError:
        raise HTTPException(503, 'Invalid scan limit configuration') from None
    with _lock:
        if _active is not None:
            raise HTTPException(409, 'A scan is already active on this server')
        _active = Control(timeout, scan_id)
    # Attempt DB lease acquisition when we know the job id.
    if scan_id is not None:
        try:
            with SessionLocal() as db:
                if not acquire_lease(db, scan_id):
                    release(_active)
                    raise HTTPException(409, 'Scan job already has an active worker lease')
                db.commit()
        except HTTPException:
            raise
        except Exception:
            logger.exception("Lease acquisition failed")
            release(_active)
            raise HTTPException(503, 'Unable to acquire scan lease') from None
    return _active


def claim(control: Control, scan_id: int) -> None:
    """Attach a persisted job to a reserved slot and acquire its durable lease."""
    with _lock:
        if _active is not control:
            raise HTTPException(409, 'Scan slot is no longer active')
        control.scan_id = scan_id
    try:
        with SessionLocal() as db:
            if not acquire_lease(db, scan_id):
                raise HTTPException(409, 'Scan job already has an active worker lease')
            db.commit()
    except Exception:
        release(control)
        raise


def release(control: Control) -> None:
    global _active
    with _lock:
        if _active is not control:
            return
        _active = None
    # Release DB lease if we hold one.
    if control.scan_id is not None:
        try:
            with SessionLocal() as db:
                release_lease(db, control.scan_id)
                db.commit()
        except Exception:
            logger.exception("Lease release failed")


def request_cancel(scan_id: int) -> None:
    with _lock:
        if _active is None or _active.scan_id != scan_id:
            raise HTTPException(409, 'Scan is not active on this server')
        _active.cancel.set()


def _finish_if_active(scan_id: int, status: str, message: str) -> None:
    with SessionLocal() as db:
        job = db.get(ScanJobDB, scan_id)
        if job is not None and job.status in {'pending', 'queued', 'running'}:
            job.status = status
            job.finished_at = datetime.now(timezone.utc)
            job.blind_spots = [message]
            db.commit()
            logger.info("Scan job finished", extra={"extra_data": {"scan_id": scan_id, "status": status}})
            try:
                record_audit("scan.finished", f"scan:{scan_id}", "system", {"status": status})
            except Exception:
                pass  # audit failures must not break job cleanup


def worker_command(repo_path: str, scan_id: int) -> list[str]:
    return [sys.executable, '-m', 'backend.scan_worker', repo_path, str(scan_id)]


def supervise(repo_path: str, control: Control) -> None:
    process = None
    status, message = 'failed', 'Scan worker failed; results are incomplete'
    try:
        if control.cancel.is_set():
            status, message = 'cancelled', 'Scan cancelled before execution'
            return
        started = time.monotonic()
        process = subprocess.Popen(
            worker_command(repo_path, control.scan_id),
            cwd=str(Path(__file__).resolve().parents[2]), stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
        )
        while process.poll() is None:
            if control.cancel.wait(0.05):
                status, message = 'cancelled', 'Scan cancelled; results are incomplete'
                break
            if time.monotonic() - started >= control.timeout:
                status, message = 'timed_out', 'Scan exceeded its time limit; results are incomplete'
                break
    except Exception:
        # Do not expose command paths, inherited configuration, or source text.
        status, message = 'failed', 'Unable to run scan worker; results are incomplete'
    finally:
        try:
            try:
                if process is not None:
                    if process.poll() is None:
                        process.kill()
                    process.wait(timeout=10)
            except Exception:
                status = 'failed'
                message = 'Unable to confirm scan worker termination; results are incomplete'
            finally:
                _finish_if_active(control.scan_id, status, message)
        finally:
            release(control)
