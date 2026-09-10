"""
FastAPI application entrypoint.

Mounts CORS, initialises DB tables on startup, and exposes three routers:
    /api/scan, /api/assets, /api/dashboard
"""

import json
import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root (ECDAT-SIH/.env) before any module reads os.environ.
_project_root = Path(__file__).resolve().parent.parent
load_dotenv(_project_root / ".env", override=False)

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import Response
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.base import BaseHTTPMiddleware

from backend.logging_config import get_logger, RequestIdFilter
from backend.security import current_role
from backend.db import Base, engine
from backend.routers.scan import router as scan_router
from backend.routers.assets import router as assets_router
from backend.routers.dashboard import router as dashboard_router
from backend.routers.outputs import router as outputs_router
from backend.routers.audit import router as audit_router
from backend.routers.auth import router as auth_router
import backend.models.scan_lease as _scan_lease  # registers the scan lease table  # noqa: F401
import backend.models.audit_log as _audit_log  # registers the audit table  # noqa: F401

logger = get_logger("ecdat.app")

SCHEMA_REVISION = "f9c6d3a18b72"
REQUIRED_TABLES = {"scan_jobs", "crypto_assets", "scan_failures", "audit_logs", "scan_leases"}


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Generate/propagate X-Request-ID and inject into thread-local logger."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        RequestIdFilter.set_request_id(request_id)
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("Unhandled exception during request processing")
            raise
        else:
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            RequestIdFilter.clear_request_id()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if os.getenv("ECDAT_AUTO_CREATE_TABLES", "true").lower() == "true":
        Base.metadata.create_all(bind=engine)
        logger.info("DB tables ensured via create_all")
    else:
        logger.info("Skipping create_all — migrations manage schema")

    # Stale-scan recovery on startup (dry-run by default).
    _recover = os.getenv("ECDAT_RECOVER_STALE_JOBS", "false").lower() == "true"
    if _recover:
        try:
            from backend.services.stale_job_recovery import recover_stale_jobs
            count = recover_stale_jobs(dry_run=False)
            logger.info("Stale-job recovery complete", extra={"extra_data": {"recovered": count}})
        except Exception:
            logger.exception("Stale-job recovery failed")
    else:
        logger.info("Stale-job recovery skipped (dry-run mode — set ECDAT_RECOVER_STALE_JOBS=true to apply)")

    # Reconcile expired DB-backed scan leases on startup.
    try:
        from backend.db import SessionLocal
        from backend.services.scan_lease import reconcile_expired_leases
        with SessionLocal() as db:
            count = reconcile_expired_leases(db)
            db.commit()
        logger.info("Startup lease reconciliation complete", extra={"extra_data": {"reconciled": count}})
    except Exception:
        logger.exception("Startup lease reconciliation failed")

    yield


app = FastAPI(
    title="ECDAT",
    description="Enterprise Cryptographic Discovery & Analysis Tool — Smart India Hackathon 2026",
    version="1.0.0",
    lifespan=lifespan,
)


@app.exception_handler(RequestValidationError)
async def invalid_request(_request, exc: RequestValidationError):
    # Never reflect passwords/raw bodies or invalid Unicode into error responses.
    details = [{"loc": error["loc"], "type": error["type"],
                "msg": "Invalid request value"} for error in exc.errors()]
    return Response(json.dumps({"detail": details}, ensure_ascii=True),
                    status_code=422, media_type="application/json")


# ── Middleware ────────────────────────────────────────────────────────────────
app.add_middleware(RequestIdMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv(
        "ECDAT_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",") if origin.strip()],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count", "X-Request-ID"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(scan_router, dependencies=[Depends(current_role)])
app.include_router(assets_router, dependencies=[Depends(current_role)])
app.include_router(dashboard_router, dependencies=[Depends(current_role)])
app.include_router(outputs_router, dependencies=[Depends(current_role)])
app.include_router(audit_router)
app.include_router(auth_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "ecdat-backend", "version": app.version}


@app.get("/ready")
def readiness() -> dict:
    """Confirm that both the API process and database are ready for a demo scan."""
    from backend.db import SessionLocal

    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        tables = set(inspect(db.get_bind()).get_table_names())
        if not REQUIRED_TABLES.issubset(tables):
            raise HTTPException(503, "Database schema is missing or incomplete")
        if os.getenv("ECDAT_AUTO_CREATE_TABLES", "true").lower() != "true":
            revision = db.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
            if revision != SCHEMA_REVISION:
                raise HTTPException(503, "Database schema migration is not current")
        return {"status": "ready", "database": "reachable"}
    except HTTPException:
        raise
    except SQLAlchemyError:
        raise HTTPException(503, "Database is unavailable or schema validation failed") from None
    finally:
        db.close()
