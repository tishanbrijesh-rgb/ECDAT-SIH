"""Assets router — list and retrieve crypto assets."""
from fastapi import APIRouter, Depends, HTTPException, Query

from backend.db import SessionLocal
from backend.models.asset import CryptoAssetDB
from backend.models.scan_job import ScanJobDB
from backend.schemas.asset import AssetResponse, AssetUpdate
from backend.security import current_role, ensure_write_role, record_audit

router = APIRouter(prefix="/api", tags=["assets"])


@router.get("/assets", response_model=list[AssetResponse])
def list_assets(scan_job_id: int | None = Query(default=None)) -> list[AssetResponse]:
    """List assets from the requested scan, or the latest completed scan by default."""
    db = SessionLocal()
    try:
        q = db.query(CryptoAssetDB)
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
            return []
        q = q.filter(CryptoAssetDB.scan_job_id == target_scan_id)
        assets = q.order_by(CryptoAssetDB.id.desc()).all()
        return [AssetResponse.model_validate(a) for a in assets]
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
