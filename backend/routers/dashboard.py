"""Dashboard router — aggregated summary statistics."""

from fastapi import APIRouter, Query

from backend.db import SessionLocal
from backend.logging_config import get_logger
from backend.models.asset import CryptoAssetDB
from backend.models.scan_job import ScanJobDB
from backend.schemas.asset import DashboardSummary

router = APIRouter(prefix="/api", tags=["dashboard"])
logger = get_logger("ecdat.dashboard")


@router.get("/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary(scan_id: int | None = Query(None)) -> DashboardSummary:
    """Return dashboard aggregation data, optionally filtered by scan."""
    db = SessionLocal()
    try:
        latest = (
            db.query(ScanJobDB).filter(ScanJobDB.status == "completed").order_by(ScanJobDB.id.desc()).first()
            if scan_id is None
            else db.query(ScanJobDB)
            .filter(ScanJobDB.id == scan_id, ScanJobDB.status == "completed")
            .first()
        )
        if not latest:
            return DashboardSummary(
                total_assets=0, high_risk_count=0, avg_confidence=0.0, coverage_pct=0.0,
                blind_spots=["No completed scan found"], risk_distribution={"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0},
                quantum_vulnerable_count=0, conflict_count=0, confirmed_use_count=0, capability_only_count=0,
                latest_scan_id=None, collector_stats={},
                confidence_distribution={"0-20": 0, "21-40": 0, "41-60": 0, "61-80": 0, "81-100": 0},
            )
        assets = db.query(CryptoAssetDB).filter(CryptoAssetDB.scan_job_id == latest.id).all()
        total_assets = len(assets)

        risk_dist: dict[str, int] = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
        high_risk = 0
        quantum_vulnerable = 0
        conflict_count = 0
        confirmed_use_count = 0
        capability_only_count = 0
        confidences: list[float] = []
        confidence_distribution = {"0-20": 0, "21-40": 0, "41-60": 0, "61-80": 0, "81-100": 0}

        for a in assets:
            label = a.priority_label or "LOW"
            risk_dist[label] = risk_dist.get(label, 0) + 1
            if label in ("CRITICAL", "HIGH"):
                high_risk += 1
            confidences.append(a.confidence)
            confidence = max(0.0, min(1.0, float(a.confidence or 0.0)))
            if confidence <= 0.2:
                confidence_distribution["0-20"] += 1
            elif confidence <= 0.4:
                confidence_distribution["21-40"] += 1
            elif confidence <= 0.6:
                confidence_distribution["41-60"] += 1
            elif confidence <= 0.8:
                confidence_distribution["61-80"] += 1
            else:
                confidence_distribution["81-100"] += 1
            quantum_vulnerable += int(bool(a.quantum_vulnerable))
            conflict_count += int(bool(a.conflict))
            confirmed_use_count += int(bool(a.confirmed_use))
            capability_only_count += int(bool(a.capability_only))

        avg_conf = round(sum(confidences) / len(confidences), 4) if confidences else 0.0

        blind_spots = list(latest.blind_spots or [])

        logger.debug("Dashboard summary computed", extra={"extra_data": {
            "scan_id": latest.id, "total_assets": total_assets, "high_risk": high_risk,
        }})

        return DashboardSummary(
            total_assets=total_assets,
            high_risk_count=high_risk,
            avg_confidence=avg_conf,
            coverage_pct=latest.coverage_pct,
            blind_spots=blind_spots,
            risk_distribution=risk_dist,
            quantum_vulnerable_count=quantum_vulnerable,
            conflict_count=conflict_count,
            confirmed_use_count=confirmed_use_count,
            capability_only_count=capability_only_count,
            latest_scan_id=latest.id,
            collector_stats=dict(latest.collector_stats or {}),
            confidence_distribution=confidence_distribution,
        )
    finally:
        db.close()
