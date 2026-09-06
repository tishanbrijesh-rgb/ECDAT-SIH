"""Single-server-process scan admission and supervised child execution."""
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
from backend.db import SessionLocal
from backend.models.scan_job import ScanJobDB
from scanner.limits import positive_int, max_file_bytes


@dataclass
class Control:
    timeout: int
    scan_id: int | None = None
    cancel: threading.Event = field(default_factory=threading.Event)


_lock = threading.Lock()
_active: Control | None = None


def reserve() -> Control:
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
        _active = Control(timeout)
        return _active


def release(control: Control) -> None:
    global _active
    with _lock:
        if _active is control:
            _active = None


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
