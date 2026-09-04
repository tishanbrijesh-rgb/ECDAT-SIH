"""
Scanner runner — orchestrates the full scan pipeline inside the FastAPI
process: scan -> correlate -> confidence -> risk -> persist.
"""

from __future__ import annotations

import os
import sys
import traceback
from datetime import datetime, timezone
from typing import Any

# Ensure the scanner package is importable (it is volume-mounted at /scanner)
_SCANNER_ROOT = os.getenv("SCANNER_PATH", "/scanner")
if _SCANNER_ROOT not in sys.path:
    sys.path.insert(0, _SCANNER_ROOT)

from scanner.main import scan_with_metrics
from scanner.main import _print as _scanner_print

from backend.models.scan_job import ScanJobDB
from backend.models.asset import CryptoAssetDB
from backend.db import SessionLocal
from backend.services.correlator import correlate
from backend.services.confidence import score_finding
from backend.services.risk_engine import assess_risk


def run_scan(repo_path: str, scan_id: int | None = None) -> dict[str, Any]:
    """
    Execute the full scan pipeline and persist results.

    Returns a summary dict:
        {
          "scan_id": int,
          "status": "completed",
          "assets_found": int,
          "avg_confidence": float,
        }
    """
    # 1. Create or claim a queued job
    db = SessionLocal()
    try:
        if scan_id is None:
            job = ScanJobDB(repo_path=repo_path, status="running")
            db.add(job)
        else:
            job = db.query(ScanJobDB).filter(ScanJobDB.id == scan_id).first()
            if job is None:
                raise ValueError(f"Scan job {scan_id} does not exist")
            job.status = "running"
        db.commit()
        db.refresh(job)
        scan_id = job.id
    finally:
        db.close()

    _scanner_print(f"Job {scan_id}: starting scan of {repo_path}")

    # 2. Run scanner
    try:
        evidence, metrics = scan_with_metrics(repo_path)
    except Exception:
        _scanner_print(f"Job {scan_id}: SCANNER CRASHED")
        traceback.print_exc()
        db = SessionLocal()
        try:
            job = db.query(ScanJobDB).filter(ScanJobDB.id == scan_id).first()
            job.status = "failed"
            job.finished_at = datetime.now(timezone.utc)
            db.commit()
        finally:
            db.close()
        return {"scan_id": scan_id, "status": "failed", "assets_found": 0,
                "avg_confidence": 0.0}

    # 3. Correlate
    findings = correlate(evidence)
    _scanner_print(f"Job {scan_id}: {len(findings)} correlated findings")

    # 4. Score & risk-assess each finding, persist
    db = SessionLocal()
    persisted = 0
    confidences: list[float] = []
    try:
        for f in findings:
            f = dict(f)  # shallow copy
            sc = score_finding(f)
            f["confidence"] = sc["confidence"]
            confidences.append(sc["confidence"])
            f.update({
                "business_criticality": "medium", "data_sensitivity": "medium",
                "data_lifetime_years": 10, "migration_time_years": 3,
                "threat_horizon_years": 15, "exposure": "internal",
                "migration_effort": "medium",
            })
            risk = assess_risk(f)
            f.update(risk)

            asset = CryptoAssetDB(
                scan_job_id=scan_id,
                algorithm=f.get("algorithm", ""),
                category=f.get("category", ""),
                source=list(f.get("sources", [])),
                location=f.get("location", ""),
                evidence_json={
                    "component": f.get("component", "repository-root"),
                    "confidence_by_source": f.get("confidence_by_source", {}),
                    "evidence_list": f.get("evidence_list", []),
                    "reasons": sc.get("reasons", []),
                    "conflicting_operations": f.get("conflicting_operations", []),
                },
                confidence=sc["confidence"],
                conflict=f.get("conflict", False),
                quantum_vulnerable=risk["quantum_vulnerable"],
                priority_score=risk["priority_score"],
                priority_label=risk["priority_label"],
                pqc_candidate=risk["pqc_candidate"],
                business_criticality="medium",
                usage=f.get("usage", "unknown"),
                library=f.get("library", ""),
                protocol=f.get("protocol", ""),
                key_size=f.get("key_size"),
                data_sensitivity="medium",
                data_lifetime_years=10,
                migration_time_years=3,
                threat_horizon_years=15,
                exposure="internal",
                migration_effort="medium",
                risk_reasons=risk["risk_reasons"],
                hybrid_recommended=risk["hybrid_recommended"],
                logical_asset_id=f.get("logical_asset_id", ""),
            )
            db.add(asset)
            persisted += 1

        avg_conf = round(sum(confidences) / len(confidences), 4) if confidences else 0.0
        job = db.query(ScanJobDB).filter(ScanJobDB.id == scan_id).first()
        job.finished_at = datetime.now(timezone.utc)
        job.status = "completed"
        job.assets_found = persisted
        job.avg_confidence = avg_conf
        job.total_files = metrics["total_files"]
        job.in_scope_files = metrics["in_scope_files"]
        job.scanned_files = metrics["scanned_files"]
        job.failed_files = metrics["failed_files"]
        job.coverage_pct = metrics["coverage_pct"]
        job.duration_ms = metrics["duration_ms"]
        job.collector_stats = metrics["collector_stats"]
        job.blind_spots = metrics["blind_spots"]
        db.commit()
        _scanner_print(f"Job {scan_id}: done — {persisted} assets, avg confidence {avg_conf:.2%}")
    finally:
        db.close()

    return {
        "scan_id": scan_id,
        "status": "completed",
        "assets_found": persisted,
        "avg_confidence": avg_conf if confidences else 0.0,
        "coverage_pct": metrics["coverage_pct"],
        "collector_stats": metrics["collector_stats"],
    }
