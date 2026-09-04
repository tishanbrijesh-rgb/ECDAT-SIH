"""Scan router — start scans and query scan job history."""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field, StrictStr


class ScanRequest(BaseModel):
    repo_path: StrictStr = Field(min_length=1, max_length=4096)

from backend.db import SessionLocal
from backend.models.scan_job import ScanJobDB
from backend.schemas.asset import ScanJobResponse
from backend.services.scanner_runner import run_scan
from backend.services.repository_guard import resolve_repository
from backend.security import current_role, ensure_write_role, record_audit

router = APIRouter(prefix="/api", tags=["scan"])


@router.post("/scan", response_model=dict)
def post_scan(payload: ScanRequest, background_tasks: BackgroundTasks, role: str = Depends(current_role)) -> dict:
    """Start a new scan. Body: {"repo_path": "..."}."""
    repo_path = payload.repo_path
    if not repo_path:
        raise HTTPException(400, detail="repo_path is required")
    ensure_write_role(role)
    repo_path = resolve_repository(repo_path)
    db = SessionLocal()
    try:
        job = ScanJobDB(repo_path=repo_path, status="queued")
        db.add(job); db.commit(); db.refresh(job)
        scan_id = job.id
    finally:
        db.close()
    background_tasks.add_task(run_scan, repo_path, scan_id)
    record_audit("scan.started", f"scan:{scan_id}", role, {"repo_path": repo_path})
    return {"scan_id": scan_id, "status": "started"}


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
