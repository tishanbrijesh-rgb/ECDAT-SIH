"""Assets router — list and retrieve crypto assets."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy import or_

from backend.db import SessionLocal
from backend.models.asset import CryptoAssetDB
from backend.models.scan_job import ScanJobDB
from backend.schemas.asset import AssetResponse, AssetUpdate
from backend.security import current_role, ensure_write_role, record_audit

router = APIRouter(prefix="/api", tags=["assets"])


@router.get("/assets", response_model=list[AssetResponse])
def list_assets(
    scan_job_id: int | None = Query(default=None, ge=1),
    limit: int | None = Query(default=None, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    search: str | None = Query(
        default=None, alias="q", min_length=1, max_length=200, pattern=r".*\S.*"
    ),
    risk: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"] | None = Query(default=None),
    quantum: bool | None = Query(default=None),
    sort: Literal["priority", "confidence", "algorithm"] = Query(default="priority"),
) -> JSONResponse:
    """List assets, with optional server-side filtering and pagination.

    Omitting ``limit`` preserves the original unpaginated response.  The
    ``X-Total-Count`` header always describes the filtered result set before
    pagination.
    """
    db = SessionLocal()
    try:
        target_scan_id = scan_job_id
        if target_scan_id is None:
            latest = (
                db.query(ScanJobDB)
                .filter(ScanJobDB.status == "completed")
                .order_by(ScanJobDB.id.desc())
                .first()
            )
            target_scan_id = latest.id if latest else None
        if target_scan_id is None:
            return JSONResponse(content=[], headers={"X-Total-Count": "0"})
        q = db.query(CryptoAssetDB).filter(CryptoAssetDB.scan_job_id == target_scan_id)
        if search_text := (search.strip() if search else ""):
            escaped = search_text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            pattern = f"%{escaped}%"
            q = q.filter(or_(
                CryptoAssetDB.algorithm.ilike(pattern, escape="\\"),
                CryptoAssetDB.category.ilike(pattern, escape="\\"),
                CryptoAssetDB.location.ilike(pattern, escape="\\"),
                CryptoAssetDB.library.ilike(pattern, escape="\\"),
                CryptoAssetDB.protocol.ilike(pattern, escape="\\"),
                CryptoAssetDB.usage.ilike(pattern, escape="\\"),
            ))
        if risk is not None:
            q = q.filter(CryptoAssetDB.priority_label == risk)
        if quantum is not None:
            q = q.filter(CryptoAssetDB.quantum_vulnerable.is_(quantum))
        total = q.count()
        if offset >= total:
            return JSONResponse(content=[], headers={"X-Total-Count": str(total)})
        if sort == "confidence":
            q = q.order_by(CryptoAssetDB.confidence.desc(), CryptoAssetDB.id.desc())
        elif sort == "algorithm":
            q = q.order_by(CryptoAssetDB.algorithm.asc(), CryptoAssetDB.id.desc())
        else:
            q = q.order_by(CryptoAssetDB.priority_score.desc(), CryptoAssetDB.id.desc())
        q = q.offset(offset)
        if limit is not None:
            q = q.limit(limit)
        assets = q.all()
        validated = [AssetResponse.model_validate(a) for a in assets]
        return JSONResponse(
            content=[a.model_dump(mode="json") for a in validated],
            headers={"X-Total-Count": str(total)},
        )
    finally:
        db.close()


@router.get("/assets/{asset_id}", response_model=AssetResponse)
def get_asset(asset_id: int) -> AssetResponse:
    """Get a single asset with full evidence detail."""
    db = SessionLocal()
    try:
        asset = db.query(CryptoAssetDB).filter(CryptoAssetDB.id == asset_id).first()
        if not asset:
            raise HTTPException(404, detail="Asset not found")
        return AssetResponse.model_validate(asset)
    finally:
        db.close()


@router.patch("/assets/{asset_id}", response_model=AssetResponse)
def update_asset(asset_id: int, payload: AssetUpdate, role: str = Depends(current_role)) -> AssetResponse:
    """Update asset fields — e.g. business_criticality."""
    from backend.services.risk_engine import assess_risk

    db = SessionLocal()
    try:
        ensure_write_role(role)
        asset = db.query(CryptoAssetDB).filter(CryptoAssetDB.id == asset_id).first()
        if not asset:
            raise HTTPException(404, detail="Asset not found")

        changes = payload.model_dump(exclude_none=True)
        for field, value in changes.items():
            setattr(asset, field, value)
        risk = assess_risk({
            "algorithm": asset.algorithm, "usage": asset.usage,
            "business_criticality": asset.business_criticality,
            "data_sensitivity": asset.data_sensitivity,
            "data_lifetime_years": asset.data_lifetime_years,
            "migration_time_years": asset.migration_time_years,
            "threat_horizon_years": asset.threat_horizon_years,
            "exposure": asset.exposure, "migration_effort": asset.migration_effort,
        })
        asset.priority_score = risk["priority_score"]
        asset.priority_label = risk["priority_label"]
        asset.pqc_candidate = risk["pqc_candidate"]
        asset.quantum_vulnerable = risk["quantum_vulnerable"]
        asset.risk_reasons = risk["risk_reasons"]
        asset.hybrid_recommended = risk["hybrid_recommended"]

        db.commit()
        db.refresh(asset)
        record_audit("asset.risk_context_updated", f"asset:{asset_id}", role, changes)
        return AssetResponse.model_validate(asset)
    finally:
        db.close()
