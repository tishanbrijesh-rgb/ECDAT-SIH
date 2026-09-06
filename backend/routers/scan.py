"""Scan router — start scans and query scan job history."""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field, StrictStr


class ScanRequest(BaseModel):
    repo_path: StrictStr = Field(min_length=1, max_length=4096)

from backend.db import SessionLocal
from backend.models.scan_job import ScanJobDB
from backend.schemas.asset import ScanJobResponse
from backend.services.repository_guard import resolve_repository
from backend.security import current_role, ensure_write_role, record_audit
from backend.services.scan_control import reserve, release, supervise, request_cancel, _finish_if_active

router = APIRouter(prefix="/api", tags=["scan"])


@router.post("/scan", response_model=dict)
def post_scan(payload: ScanRequest, background_tasks: BackgroundTasks, role: str = Depends(current_role)) -> dict:
    """Start a new scan. Body: {"repo_path": "..."}."""
    repo_path = payload.repo_path
    if not repo_path:
        raise HTTPException(400, detail="repo_path is required")
    ensure_write_role(role)
    repo_path = resolve_repository(repo_path)
    control = reserve()
    db = None
    try:
        db = SessionLocal()
        job = ScanJobDB(repo_path=repo_path, status="queued")
        db.add(job); db.commit(); db.refresh(job)
        scan_id = job.id
        control.scan_id = scan_id
    except Exception:
        try:
            if control.scan_id is not None:
                _finish_if_active(control.scan_id, 'failed', 'Scan submission failed before worker launch')
        finally:
            release(control)
        raise
    finally:
        if db is not None:
            db.close()
    try:
        record_audit("scan.started", f"scan:{scan_id}", role, {"repo_path": repo_path})
        background_tasks.add_task(supervise, repo_path, control)
    except Exception:
        try:
            _finish_if_active(scan_id, 'failed', 'Scan submission failed before worker launch')
        finally:
            release(control)
        raise
    return {"scan_id": scan_id, "status": "started"}


@router.post('/scans/{scan_id}/cancel', status_code=202)
def cancel_scan(scan_id: int, role: str = Depends(current_role)) -> dict:
    ensure_write_role(role)
    with SessionLocal() as db:
        job = db.get(ScanJobDB, scan_id)
        if job is None:
            raise HTTPException(404, 'Scan job not found')
        if job.status not in {'pending', 'queued', 'running'}:
            raise HTTPException(409, 'Scan is already finished')
    request_cancel(scan_id)
    record_audit('scan.cancel_requested', f'scan:{scan_id}', role, {})
    return {'scan_id': scan_id, 'status': 'cancellation_requested'}


@router.get("/scans", response_model=list[ScanJobResponse])
def list_scans() -> list[ScanJobResponse]:
    """List all scan jobs, most recent first."""
    db = SessionLocal()
    try:
        jobs = db.query(ScanJobDB).order_by(ScanJobDB.id.desc()).all()
        return [ScanJobResponse.model_validate(j) for j in jobs]
    finally:
        db.close()


@router.get("/scans/{scan_id}", response_model=ScanJobResponse)
def get_scan(scan_id: int) -> ScanJobResponse:
    """Get a single scan job detail."""
    db = SessionLocal()
    try:
        job = db.query(ScanJobDB).filter(ScanJobDB.id == scan_id).first()
        if not job:
            raise HTTPException(404, detail="Scan job not found")
        return ScanJobResponse.model_validate(job)
    finally:
        db.close()
