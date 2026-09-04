"""CBOM, risk-report, evidence-graph, and evaluation output endpoints."""
from __future__ import annotations
from collections import Counter
from fastapi import APIRouter, HTTPException, Response
from backend.db import SessionLocal
from backend.models.asset import CryptoAssetDB
from backend.models.scan_job import ScanJobDB
from backend.services.evaluation import evaluate_assets

router = APIRouter(prefix="/api", tags=["outputs"])

def _scan_and_assets(db, scan_id: int | None):
    scan = db.query(ScanJobDB).filter(ScanJobDB.id == scan_id).first() if scan_id else db.query(ScanJobDB).filter(ScanJobDB.status == "completed").order_by(ScanJobDB.id.desc()).first()
    if not scan:
        raise HTTPException(404, "No completed scan found")
    return scan, db.query(CryptoAssetDB).filter(CryptoAssetDB.scan_job_id == scan.id).all()

@router.get("/cbom")
def cbom(scan_id: int | None = None) -> dict:
    db = SessionLocal()
    try:
        scan, assets = _scan_and_assets(db, scan_id)
        return {
            "bomFormat": "CycloneDX", "specVersion": "1.6", "version": 1,
            "serialNumber": f"urn:uuid:ecdat-scan-{scan.id}", "scan_id": scan.id,
            "metadata": {"tool": {"name": "ECDAT", "version": "1.0.0"}, "repository": scan.repo_path, "coverage_pct": scan.coverage_pct},
            "components": [{
                "id": asset.logical_asset_id, "type": "cryptographic-asset",
                "name": asset.algorithm, "category": asset.category, "usage": asset.usage,
                "location": asset.location, "library": asset.library, "protocol": asset.protocol,
                "key_size": asset.key_size, "evidence_sources": asset.source,
                "confidence": asset.confidence, "quantum_vulnerable": asset.quantum_vulnerable,
            } for asset in assets],
        }
    finally: db.close()

@router.get("/reports/risk")
def risk_report(scan_id: int | None = None) -> dict:
    db = SessionLocal()
    try:
        scan, assets = _scan_and_assets(db, scan_id)
        distribution = Counter(asset.priority_label for asset in assets)
        ranked = sorted(assets, key=lambda asset: asset.priority_score, reverse=True)
        return {
            "title": "ECDAT Cryptographic Risk and PQC Migration Report", "scan_id": scan.id,
            "repository": scan.repo_path, "coverage_pct": scan.coverage_pct,
            "summary": {"assets": len(assets), "quantum_vulnerable": sum(a.quantum_vulnerable for a in assets), "conflicts": sum(a.conflict for a in assets), "risk_distribution": dict(distribution)},
            "blind_spots": scan.blind_spots or [],
            "migration_priorities": [{"asset_id": a.id, "algorithm": a.algorithm, "location": a.location, "score": a.priority_score, "label": a.priority_label, "reasons": a.risk_reasons, "recommendation": a.pqc_candidate, "hybrid": a.hybrid_recommended} for a in ranked],
        }
    finally: db.close()

@router.get("/evidence-graph")
def evidence_graph(scan_id: int | None = None) -> dict:
    db = SessionLocal()
    try:
        scan, assets = _scan_and_assets(db, scan_id)
        nodes, edges = [], []
        for asset in assets:
            asset_node = f"asset:{asset.id}"
            nodes.append({"id": asset_node, "type": "asset", "label": asset.algorithm, "confidence": asset.confidence})
            for source in asset.source:
                source_node = f"source:{asset.id}:{source}"
                nodes.append({"id": source_node, "type": "evidence", "label": source.upper()})
                edges.append({"source": source_node, "target": asset_node, "relation": "supports"})
        return {"scan_id": scan.id, "nodes": nodes, "edges": edges}
    finally: db.close()

@router.get("/evaluation")
def evaluation(scan_id: int | None = None) -> dict:
    db = SessionLocal()
    try:
        scan, assets = _scan_and_assets(db, scan_id)
        result = evaluate_assets(assets, scan.repo_path)
        result.update({"scan_id": scan.id, "coverage_pct": scan.coverage_pct, "duration_ms": scan.duration_ms})
        return result
    finally: db.close()

@router.get("/reports/risk.txt")
def risk_report_text(scan_id: int | None = None) -> Response:
    report = risk_report(scan_id)
    lines = [report["title"], f"Repository: {report['repository']}", f"Coverage: {report['coverage_pct']}%", "", "Migration priorities:"]
    lines.extend(f"P{index + 1} | {item['label']} {item['score']}/100 | {item['algorithm']} | {item['location']} | {item['recommendation']}" for index, item in enumerate(report["migration_priorities"]))
    return Response("\n".join(lines), media_type="text/plain", headers={"Content-Disposition": "attachment; filename=ecdat-risk-report.txt"})
