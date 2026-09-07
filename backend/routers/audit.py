"""Read-only audit history endpoint for auditors and administrators."""
from fastapi import APIRouter, Depends, HTTPException, Query
from backend.db import SessionLocal
from backend.models.audit_log import AuditLogDB
from backend.security import current_role

router = APIRouter(prefix="/api", tags=["audit"])

@router.get("/audit-logs")
def audit_logs(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    role: str = Depends(current_role),
) -> list[dict]:
    if role not in {"admin", "auditor"}:
        raise HTTPException(403, "Audit history requires Admin or Auditor role")
    db = SessionLocal()
    try:
        rows = (
            db.query(AuditLogDB)
            .order_by(AuditLogDB.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [{"id":r.id,"timestamp":r.timestamp,"actor_role":r.actor_role,"action":r.action,"resource":r.resource,"details":r.details} for r in rows]
    finally: db.close()
