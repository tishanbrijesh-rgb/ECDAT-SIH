"""Dashboard router — aggregated summary statistics."""
from fastapi import APIRouter

from backend.db import SessionLocal
from backend.models.asset import CryptoAssetDB
from backend.models.scan_job import ScanJobDB
from backend.schemas.asset import DashboardSummary

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary() -> DashboardSummary:
    """Return dashboard aggregation data."""
    db = SessionLocal()
    try:
        latest = db.query(ScanJobDB).filter(ScanJobDB.status == "completed").order_by(ScanJobDB.id.desc()).first()
        # Dashboard figures describe one coherent snapshot: the latest completed scan.
        assets = (
            db.query(CryptoAssetDB).filter(CryptoAssetDB.scan_job_id == latest.id).all()
            if latest else []
        )
        total_assets = len(assets)

        # Risk distribution and high-risk count
        risk_dist: dict[str, int] = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
        high_risk = 0
        quantum_vulnerable = 0
        conflict_count = 0
        confidences: list[float] = []

        for a in assets:
            label = a.priority_label or "LOW"
            risk_dist[label] = risk_dist.get(label, 0) + 1
            if label in ("CRITICAL", "HIGH"):
                high_risk += 1
            confidences.append(a.confidence)
            quantum_vulnerable += int(bool(a.quantum_vulnerable))
            conflict_count += int(bool(a.conflict))

        avg_conf = round(sum(confidences) / len(confidences), 4) if confidences else 0.0

        blind_spots = list(latest.blind_spots or []) if latest else ["No completed scan is available to measure visibility"]

        return DashboardSummary(
            total_assets=total_assets,
            high_risk_count=high_risk,
            avg_confidence=avg_conf,
            coverage_pct=latest.coverage_pct if latest else 0.0,
            blind_spots=blind_spots,
            risk_distribution=risk_dist,
            quantum_vulnerable_count=quantum_vulnerable,
            conflict_count=conflict_count,
            latest_scan_id=latest.id if latest else None,
            collector_stats=dict(latest.collector_stats or {}) if latest else {},
        )
    finally:
        db.close()
