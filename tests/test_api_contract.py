"""Versioned API contract tests — verify that ECDAT endpoints return expected fields
and types without depending on implementation details.

These tests use the isolated_client fixture from tests/conftest.py to ensure a
clean database and proper session isolation.
"""
from __future__ import annotations

from backend.models.asset import CryptoAssetDB
from backend.models.scan_job import ScanJobDB
from tests.integration_env import PASSWORD as _CONTRACT_PASSWORD


def _require_fields(payload: dict, expected: set[str]):
    missing = expected - set(payload.keys())
    assert missing == set(), f"Missing fields: {missing}"


def _auth_headers(isolated_client):
    """Get auth headers, clearing rate limiter first."""
    from backend.middleware.rate_limit import _windows
    _windows.clear()
    resp = isolated_client.post(
        "/api/auth/login",
        json={"username": "analyst", "password": _CONTRACT_PASSWORD},
    )
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ── contract tests ───────────────────────────────────────────────────────────


def test_list_scans_returns_expected_fields(isolated_client):
    """GET /api/scans must return list of scan job objects with required fields."""
    headers = _auth_headers(isolated_client)
    resp = isolated_client.get("/api/scans", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    required = {
        "id", "repo_path", "status", "assets_found", "avg_confidence",
        "total_files", "in_scope_files", "scanned_files", "failed_files",
        "coverage_pct", "duration_ms", "collector_stats", "blind_spots",
    }
    if data:
        _require_fields(data[0], required)


def test_get_scan_detail_returns_expected_fields(isolated_client):
    """GET /api/scans/{id} must return the same required fields."""
    scan_id = _seed_scan_with_assets(isolated_client)
    headers = _auth_headers(isolated_client)
    resp = isolated_client.get(f"/api/scans/{scan_id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    required = {
        "id", "repo_path", "status", "assets_found", "avg_confidence",
        "total_files", "in_scope_files", "scanned_files", "failed_files",
        "coverage_pct", "duration_ms", "collector_stats", "blind_spots",
    }
    _require_fields(data, required)
    assert data["status"] == "completed"
    assert data["coverage_pct"] == 100.0


def test_list_assets_returns_required_fields(isolated_client):
    scan_id = _seed_scan_with_assets(isolated_client)
    headers = _auth_headers(isolated_client)
    resp = isolated_client.get(f"/api/assets?scan_job_id={scan_id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)
    items = data["items"]
    assert len(items) == 2
    required = {
        "id", "scan_job_id", "algorithm", "category", "source", "location",
        "evidence_json", "confidence", "conflict", "quantum_vulnerable",
        "priority_score", "priority_label", "pqc_candidate",
        "business_criticality", "usage", "library", "protocol", "key_size",
        "data_sensitivity", "data_lifetime_years", "migration_time_years",
        "threat_horizon_years", "exposure", "migration_effort",
        "risk_reasons", "hybrid_recommended", "logical_asset_id",
        "evidence_kind", "parser_version", "evidence_quality",
        "confirmed_use", "capability_only", "created_at",
    }
    _require_fields(items[0], required)
    assert isinstance(items[0]["evidence_kind"], str)
    assert items[0]["evidence_kind"] != ""


def test_single_asset_returns_required_fields(isolated_client):
    scan_id = _seed_scan_with_assets(isolated_client)
    headers = _auth_headers(isolated_client)
    all_assets = isolated_client.get(
        f"/api/assets?scan_job_id={scan_id}", headers=headers,
    ).json()
    asset_id = all_assets["items"][0]["id"]
    resp = isolated_client.get(f"/api/assets/{asset_id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    required = {
        "id", "algorithm", "evidence_kind", "confidence", "priority_label",
        "quantum_vulnerable", "evidence_json",
    }
    _require_fields(data, required)


def test_evidence_json_contains_expected_keys(isolated_client):
    """evidence_json must include evidence_kind and parser_version."""
    scan_id = _seed_scan_with_assets(isolated_client)
    headers = _auth_headers(isolated_client)
    resp = isolated_client.get(f"/api/assets?scan_job_id={scan_id}", headers=headers)
    data = resp.json()
    for asset in data["items"]:
        ej = asset["evidence_json"]
        assert "evidence_kind" in ej
        assert "parser_version" in ej


def test_evaluation_returns_metric_fields(isolated_client):
    scan_id = _seed_scan_with_assets(isolated_client)
    headers = _auth_headers(isolated_client)
    resp = isolated_client.get(f"/api/evaluation?scan_id={scan_id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    required = {"scan_id", "coverage_pct", "duration_ms"}
    assert required.issubset(set(data.keys()))
    if data.get("expected") is not None:
        assert "precision" in data
        assert "recall" in data
        assert "f1" in data
    assert data["scan_id"] == scan_id


def test_cbom_has_required_top_level_keys(isolated_client):
    scan_id = _seed_scan_with_assets(isolated_client)
    headers = _auth_headers(isolated_client)
    resp = isolated_client.get(f"/api/cbom?scan_id={scan_id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    required_top = {"bomFormat", "specVersion", "version", "metadata", "components"}
    assert required_top.issubset(set(data.keys()))
    assert isinstance(data["components"], list)
    assert len(data["components"]) >= 1
    component = data["components"][0]
    assert "name" in component
    assert "properties" in component


def test_cbom_component_properties_include_ecdat_fields(isolated_client):
    scan_id = _seed_scan_with_assets(isolated_client)
    headers = _auth_headers(isolated_client)
    resp = isolated_client.get(f"/api/cbom?scan_id={scan_id}", headers=headers)
    data = resp.json()
    names = {p["name"] for c in data["components"] for p in c.get("properties", [])}
    expected_props = {
        "ecdat:asset:id", "ecdat:category", "ecdat:usage",
        "ecdat:evidence-kind", "ecdat:parser-version",
        "ecdat:location", "ecdat:confidence",
    }
    assert expected_props.issubset(names), f"Missing CBOM properties: {expected_props - names}"


def test_calibration_response_shape(isolated_client):
    headers = _auth_headers(isolated_client)
    resp = isolated_client.get("/api/calibration", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    required = {"version", "band_definitions", "band_thresholds", "metrics", "last_calibrated"}
    assert required.issubset(set(data.keys()))
    assert "brier_score" in data["metrics"]
    assert "ece" in data["metrics"]


def test_dashboard_summary_fields(isolated_client):
    scan_id = _seed_scan_with_assets(isolated_client)
    headers = _auth_headers(isolated_client)
    resp = isolated_client.get(f"/api/dashboard/summary?scan_id={scan_id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    required = {
        "total_assets", "avg_confidence", "coverage_pct",
        "blind_spots", "risk_distribution", "quantum_vulnerable_count",
        "conflict_count", "collector_stats",
        "confidence_distribution",
    }
    assert required.issubset(set(data.keys()))
    assert isinstance(data["risk_distribution"], dict)
    assert isinstance(data["blind_spots"], list)
    assert data["total_assets"] == 2
    assert data["risk_distribution"] == {
        "CRITICAL": 0, "HIGH": 1, "MEDIUM": 0, "LOW": 1,
    }
    assert data["quantum_vulnerable_count"] == 1
    assert data["conflict_count"] == 0
    assert sum(data["confidence_distribution"].values()) == data["total_assets"]


def test_evidence_graph_shape(isolated_client):
    scan_id = _seed_scan_with_assets(isolated_client)
    headers = _auth_headers(isolated_client)
    resp = isolated_client.get(f"/api/evidence-graph?scan_id={scan_id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "scan_id" in data
    assert "nodes" in data
    assert "edges" in data
    assert isinstance(data["nodes"], list)
    assert isinstance(data["edges"], list)
    if data["nodes"]:
        node = data["nodes"][0]
        assert "id" in node
        assert "type" in node


# ── seeding helpers ──────────────────────────────────────────────────────────


def _seed_scan_with_assets(isolated_client):
    """Create one completed scan job with two assets and return the scan id."""
    import uuid
    repo_path = f"/contract-fixture-{uuid.uuid4().hex[:8]}"

    # Use the patched SessionLocal to insert directly into the test database
    from backend.db import SessionLocal
    db = SessionLocal()
    try:
        job = ScanJobDB(
            repo_path=repo_path,
            status="completed",
            assets_found=2,
            avg_confidence=0.85,
            coverage_pct=100.0,
            duration_ms=1500,
            total_files=10,
            in_scope_files=10,
            scanned_files=10,
            failed_files=0,
            collector_stats={"ast": 10, "rule": 5},
            blind_spots=[],
        )
        db.add(job)
        db.flush()
        scan_id = job.id
        fixtures = [
            {
                "scan_job_id": scan_id,
                "algorithm": "RSA",
                "category": "encryption",
                "source": ["rule"],
                "location": "src/crypto.py",
                "confidence": 0.95,
                "priority_score": 90,
                "priority_label": "HIGH",
                "evidence_kind": "observed_operation",
                "parser_version": "test-v1",
                "usage": "encryption",
                "library": "cryptography",
                "protocol": "TLS",
                "key_size": 2048,
                "data_sensitivity": "high",
                "business_criticality": "high",
                "quantum_vulnerable": True,
                "conflict": False,
                "risk_reasons": ["RSA is Shor-vulnerable"],
                "hybrid_recommended": True,
                "pqc_candidate": "ML-KEM",
                "logical_asset_id": f"asset-{scan_id}-0",
                "evidence_quality": "observed_operation",
                "confirmed_use": True,
                "capability_only": False,
                "span": {"file": "src/crypto.py", "line_start": 1, "line_end": 10},
                "confidence_reasons": [],
                "evidence_json": {
                    "component": "src/crypto.py",
                    "evidence_kind": "observed_operation",
                    "parser_version": "test-v1",
                    "operation_anchor": "op-1",
                },
            },
            {
                "scan_job_id": scan_id,
                "algorithm": "SHA-256",
                "category": "hash",
                "source": ["ast", "rule"],
                "location": "src/hash.py",
                "confidence": 0.80,
                "priority_score": 20,
                "priority_label": "LOW",
                "evidence_kind": "configured_protocol",
                "parser_version": "test-v1",
                "usage": "hash",
                "library": "",
                "protocol": "",
                "key_size": 256,
                "data_sensitivity": "low",
                "business_criticality": "low",
                "quantum_vulnerable": False,
                "conflict": False,
                "risk_reasons": [],
                "hybrid_recommended": False,
                "pqc_candidate": "No migration required",
                "logical_asset_id": f"asset-{scan_id}-1",
                "evidence_quality": "configured_protocol",
                "confirmed_use": True,
                "capability_only": False,
                "span": {"file": "src/hash.py", "line_start": 5, "line_end": 8},
                "confidence_reasons": [],
                "evidence_json": {
                    "component": "src/hash.py",
                    "evidence_kind": "configured_protocol",
                    "parser_version": "test-v1",
                    "operation_anchor": "op-2",
                },
            },
        ]
        for asset_data in fixtures:
            db.add(CryptoAssetDB(**asset_data))
        db.commit()
        return scan_id
    finally:
        db.close()
