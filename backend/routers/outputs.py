"""CBOM, risk-report, evidence-graph, and evaluation output endpoints."""
from __future__ import annotations
from collections import Counter
import json
from typing import Annotated
from uuid import NAMESPACE_URL, uuid5
from fastapi import APIRouter, HTTPException, Query, Response
from backend.db import SessionLocal
from backend.models.asset import CryptoAssetDB
from backend.models.scan_job import ScanJobDB
from backend.services.evaluation import evaluate_assets

router = APIRouter(prefix="/api", tags=["outputs"])
ScanId = Annotated[int | None, Query(ge=1)]

def _scan_and_assets(db, scan_id: int | None):
    if scan_id is None:
        scan = db.query(ScanJobDB).filter(ScanJobDB.status == "completed").order_by(ScanJobDB.id.desc()).first()
    else:
        scan = db.query(ScanJobDB).filter(ScanJobDB.id == scan_id).first()
        if scan is not None and scan.status != "completed":
            raise HTTPException(409, "Scan is not complete")
    if scan is None:
        raise HTTPException(404, "No completed scan found")
    return scan, db.query(CryptoAssetDB).filter(CryptoAssetDB.scan_job_id == scan.id).all()

@router.get("/cbom")
def cbom(scan_id: ScanId = None) -> dict:
    db = SessionLocal()
    try:
        scan, assets = _scan_and_assets(db, scan_id)
        def properties(asset: CryptoAssetDB) -> list[dict[str, str]]:
            evidence = asset.evidence_json or {}
            values = {
                "ecdat:asset:id": asset.logical_asset_id,
                "ecdat:category": asset.category,
                "ecdat:usage": asset.usage,
                "ecdat:operation-anchor": evidence.get("operation_anchor", ""),
                "ecdat:context-conflicts": evidence.get("context_conflicts", {}),
                "ecdat:location": asset.location,
                "ecdat:library": asset.library,
                "ecdat:protocol": asset.protocol,
                "ecdat:key-size": asset.key_size,
                "ecdat:evidence:sources": asset.source,
                "ecdat:confidence": asset.confidence,
                "ecdat:quantum-vulnerable": asset.quantum_vulnerable,
            }
            return [
                {"name": name, "value": (
                    str(value).lower() if isinstance(value, bool) else
                    json.dumps(value, sort_keys=True) if isinstance(value, (list, dict)) else
                    str(value)
                )}
                for name, value in values.items()
                if value not in (None, "", [], {})
            ]

        return {
            "$schema": "https://cyclonedx.org/schema/bom-1.6.schema.json",
            "bomFormat": "CycloneDX",
            "specVersion": "1.6",
            "serialNumber": f"urn:uuid:{uuid5(NAMESPACE_URL, f'ecdat:scan:{scan.id}')}",
            "version": 1,
            "metadata": {
                "tools": {"components": [{
                    "type": "application", "name": "ECDAT", "version": "1.0.0"
                }]},
                "properties": [
                    {"name": "ecdat:scan:id", "value": str(scan.id)},
                    {"name": "ecdat:repository:path", "value": scan.repo_path},
                    {"name": "ecdat:scan:coverage-percent", "value": str(scan.coverage_pct)},
                ],
            },
            "components": [{
                "type": "library",
                "bom-ref": f"ecdat:asset:{asset.id}",
                "name": asset.algorithm,
                "properties": properties(asset),
            } for asset in assets],
        }
    finally: db.close()

@router.get("/reports/risk")
def risk_report(scan_id: ScanId = None) -> dict:
    db = SessionLocal()
    try:
        scan, assets = _scan_and_assets(db, scan_id)
        distribution = Counter(asset.priority_label for asset in assets)
        ranked = sorted(assets, key=lambda asset: asset.priority_score, reverse=True)
        return {
            "title": "ECDAT Cryptographic Risk and PQC Migration Report", "scan_id": scan.id,
            "repository": scan.repo_path, "coverage_pct": scan.coverage_pct,
            "summary": {"assets": len(assets), "quantum_vulnerable": sum(a.quantum_vulnerable for a in assets), "conflicts": sum(a.conflict for a in assets), "risk_distribution": dict(distribution)},
            "blind_spots": list(scan.blind_spots or []),
            "migration_priorities": [{"asset_id": a.id, "logical_asset_id": a.logical_asset_id,
                "algorithm": a.algorithm, "usage": a.usage,
                "operation_anchor": (a.evidence_json or {}).get("operation_anchor", ""),
                "location": a.location, "score": a.priority_score, "label": a.priority_label,
                "reasons": a.risk_reasons, "recommendation": a.pqc_candidate,
                "hybrid": a.hybrid_recommended} for a in ranked],
        }
    finally: db.close()

@router.get("/evidence-graph")
def evidence_graph(scan_id: ScanId = None) -> dict:
    db = SessionLocal()
    try:
        scan, assets = _scan_and_assets(db, scan_id)
        nodes, edges = [], []
        for asset in assets:
            asset_node = f"asset:{asset.id}"
            nodes.append({"id": asset_node, "type": "asset", "label": f"{asset.algorithm} ({asset.usage})",
                          "logical_asset_id": asset.logical_asset_id,
                          "operation_anchor": (asset.evidence_json or {}).get("operation_anchor", ""),
                          "confidence": asset.confidence})
            for source in asset.source:
                source_node = f"source:{asset.id}:{source}"
                nodes.append({"id": source_node, "type": "evidence", "label": source.upper()})
                edges.append({"source": source_node, "target": asset_node, "relation": "supports"})
        return {"scan_id": scan.id, "nodes": nodes, "edges": edges}
    finally: db.close()

@router.get("/evaluation")
def evaluation(scan_id: ScanId = None) -> dict:
    db = SessionLocal()
    try:
        scan, assets = _scan_and_assets(db, scan_id)
        result = evaluate_assets(assets, scan.repo_path)
        result.update({"scan_id": scan.id, "coverage_pct": scan.coverage_pct, "duration_ms": scan.duration_ms})
        return result
    finally: db.close()

@router.get("/reports/risk.txt")
def risk_report_text(scan_id: ScanId = None) -> Response:
    report = risk_report(scan_id)
    lines = [report["title"], f"Repository: {report['repository']}", f"Coverage: {report['coverage_pct']}%", "", "Migration priorities:"]
    lines.extend(f"P{index + 1} | {item['label']} {item['score']}/100 | {item['algorithm']} ({item['usage']}) | {item['location']} | {item['operation_anchor']} | {item['recommendation']}" for index, item in enumerate(report["migration_priorities"]))
    return Response("\n".join(lines), media_type="text/plain", headers={"Content-Disposition": "attachment; filename=ecdat-risk-report.txt"})
