"""
FastAPI application entrypoint.

Mounts CORS, initialises DB tables on startup, and exposes three routers:
    /api/scan, /api/assets, /api/dashboard
"""

import json
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from backend.security import current_role
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import Response

from backend.db import Base, engine
from backend.routers.scan import router as scan_router
from backend.routers.assets import router as assets_router
from backend.routers.dashboard import router as dashboard_router
from backend.routers.outputs import router as outputs_router
from backend.routers.audit import router as audit_router
from backend.routers.auth import router as auth_router
import backend.models.audit_log  # registers the audit table with SQLAlchemy metadata


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    print("[ecdat] DB tables ensured")
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

# ── CORS ────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv(
        "ECDAT_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",") if origin.strip()],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count"],
)

# ── Routers ─────────────────────────────────────────────────────────────────
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
    from sqlalchemy import text
    from backend.db import SessionLocal

    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ready", "database": "reachable"}
    finally:
        db.close()
