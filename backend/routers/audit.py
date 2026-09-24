"""Read-only audit history endpoint for auditors and administrators."""
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from backend.db import SessionLocal
from backend.logging_config import get_logger
from backend.models.audit_log import AuditLogDB
from backend.security import Principal, current_role, record_audit

logger = get_logger("ecdat.audit")
router = APIRouter(prefix="/api", tags=["audit"])

_DEFAULT_RETENTION_DAYS = 90


@router.get("/audit-logs")
def audit_logs(
    role: Annotated[Principal | str, Depends(current_role)],
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> JSONResponse:
    """List audit log entries, most recent first, with pagination."""
    if role not in {"admin", "auditor"}:
        raise HTTPException(403, "Audit history requires Admin or Auditor role")
    db = SessionLocal()
    try:
        total = db.query(AuditLogDB).count()
        logger.info("Audit logs listed", extra={"extra_data": {"offset": offset, "limit": limit, "role": role}})
        rows = (
            db.query(AuditLogDB)
            .order_by(AuditLogDB.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        items = [
            {
                "id": r.id,
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                "actor_subject": r.actor_subject,
                "actor_role": r.actor_role,
                "actor_session_id": r.actor_session_id,
                "actor_expires_at": r.actor_expires_at,
                "action": r.action,
                "resource": r.resource,
                "details": r.details,
            }
            for r in rows
        ]
        return JSONResponse(content=items, headers={"X-Total-Count": str(total)})
    finally:
        db.close()


@router.delete("/audit-logs/retention/purge")
def purge_old_audit_logs(
    role: Annotated[Principal | str, Depends(current_role)],
    days: int = Query(default=_DEFAULT_RETENTION_DAYS, ge=1, le=365),
) -> dict:
    """Delete audit log entries older than *days* (admin only)."""
    if role != "admin":
        raise HTTPException(403, "Audit log purge requires Admin role")
    cutoff = datetime.now(timezone.utc).timestamp() - (days * 86400)
    cutoff_dt = datetime.fromtimestamp(cutoff, tz=timezone.utc)
    db = SessionLocal()
    try:
        deleted = (
            db.query(AuditLogDB)
            .filter(AuditLogDB.timestamp < cutoff_dt)
            .delete(synchronize_session=False)
        )
        result = {"deleted": deleted, "older_than": str(cutoff_dt)}
        record_audit(
            "audit.retention_purged",
            "audit_logs",
            role,
            {
                "days": days,
                "cutoff": result["older_than"],
                "deleted": deleted,
            },
            session=db,
        )
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
