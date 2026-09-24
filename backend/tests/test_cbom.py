"""Tests for the CBOM (CycloneDX 1.6) output endpoint."""
from __future__ import annotations

import types
import uuid

import pytest
from fastapi.testclient import TestClient

from backend.models.scan_job import ScanJobDB


@pytest.fixture(autouse=True)
def _mock_external_deps():
    """Patch filesystem-dependent and subprocess-spawning calls."""
    import backend.routers.scan as _rs
    import backend.services.repository_guard as _rg
    import backend.services.scan_control as _sc

    _orig_resolve = _rg.resolve_repository
    _rg.resolve_repository = lambda raw: raw
    _rs.resolve_repository = lambda raw: raw

    def _dummy_reserve(*_a, **_kw):
        return types.SimpleNamespace(
            scan_id=None,
            timeout=300,
            cancel=types.SimpleNamespace(is_set=lambda: False, set=lambda: None),
        )

    _orig_reserve_fn = _rs.reserve
    _rs.reserve = _dummy_reserve
    _sc.reserve = _dummy_reserve

    _orig_claim = _rs.claim
    _orig_release = _rs.release
    _orig_request_cancel = _rs.request_cancel
    _rs.claim = lambda *a, **kw: None
    _rs.release = lambda *a, **kw: None
    _rs.request_cancel = lambda scan_id: None

    yield

    _rg.resolve_repository = _orig_resolve
    _rs.resolve_repository = _orig_resolve
    _rs.reserve = _orig_reserve_fn
    _sc.reserve = _orig_reserve_fn
    _rs.claim = _orig_claim
    _rs.release = _orig_release
    _rs.request_cancel = _orig_request_cancel


def _create_completed_scan(client: TestClient, repo_path: str = "/test/repo") -> int:
    """Create a scan, mark it completed, and return its id."""
    resp = client.post("/api/scan", json={"repo_path": repo_path})
    assert resp.status_code == 200
    scan_id = resp.json()["scan_id"]

    from backend.db import SessionLocal

    with SessionLocal() as db:
        job = db.get(ScanJobDB, scan_id)
        job.status = "completed"
        job.repo_path = repo_path
        db.commit()

    return scan_id


class TestCbomEndpoint:
    """Integration tests for GET /api/cbom."""

    def _seed_assets(self, client: TestClient, scan_id: int):
        """Insert synthetic CryptoAsset rows for the given scan."""
        from backend.db import SessionLocal
        from backend.models.asset import CryptoAssetDB

        assets = [
            {
                "scan_job_id": scan_id,
                "algorithm": "RSA-2048",
                "category": "encryption",
                "source": ["file"],
                "location": "src/crypto.py",
                "confidence": 0.92,
                "conflict": False,
                "quantum_vulnerable": True,
                "priority_score": 80,
                "priority_label": "CRITICAL",
                "pqc_candidate": "Evaluate ML-KEM",
                "business_criticality": "high",
                "usage": "encryption",
                "library": "pycryptodome",
                "protocol": "TLS",
                "key_size": 2048,
                "data_sensitivity": "high",
                "data_lifetime_years": 10,
                "migration_time_years": 2,
                "threat_horizon_years": 15,
                "exposure": "internet",
                "migration_effort": "medium",
                "risk_reasons": ["RSA vulnerable to quantum attacks"],
                "hybrid_recommended": False,
                "logical_asset_id": "asset-rsa-2048",
            },
            {
                "scan_job_id": scan_id,
                "algorithm": "AES-256",
                "category": "encryption",
                "source": ["file"],
                "location": "src/crypto.py",
                "confidence": 0.85,
                "conflict": False,
                "quantum_vulnerable": False,
                "priority_score": 10,
                "priority_label": "LOW",
                "pqc_candidate": "Retain symmetric design",
                "business_criticality": "medium",
                "usage": "encryption",
                "library": "pycryptodome",
                "protocol": "TLS",
                "key_size": 256,
                "data_sensitivity": "medium",
                "data_lifetime_years": 5,
                "migration_time_years": 1,
                "threat_horizon_years": 15,
                "exposure": "internal",
                "migration_effort": "low",
                "risk_reasons": ["No quantum vulnerability"],
                "hybrid_recommended": False,
                "logical_asset_id": "asset-aes-256",
            },
            {
                "scan_job_id": scan_id,
                "algorithm": "ECDSA-P256",
                "category": "signature",
                "source": ["file"],
                "location": "src/signing.py",
                "confidence": 0.70,
                "conflict": True,
                "quantum_vulnerable": True,
                "priority_score": 60,
                "priority_label": "HIGH",
                "pqc_candidate": "Evaluate ML-DSA",
                "business_criticality": "high",
                "usage": "signature",
                "library": "openssl",
                "protocol": "TLS",
                "key_size": 256,
                "data_sensitivity": "high",
                "data_lifetime_years": 15,
                "migration_time_years": 3,
                "threat_horizon_years": 10,
                "exposure": "internet",
                "migration_effort": "high",
                "risk_reasons": ["ECDSA vulnerable", "conflicting operations"],
                "hybrid_recommended": True,
                "logical_asset_id": "asset-ecdsa-p256",
            },
            {
                "scan_job_id": scan_id,
                "algorithm": "SHA-256",
                "category": "hash",
                "source": ["file"],
                "location": "src/hashing.py",
                "confidence": 0.95,
                "conflict": False,
                "quantum_vulnerable": False,
                "priority_score": 5,
                "priority_label": "LOW",
                "pqc_candidate": "Use SHA-256/SHA-3",
                "business_criticality": "medium",
                "usage": "hash",
                "library": "stdlib",
                "protocol": "N/A",
                "key_size": None,
                "data_sensitivity": "low",
                "data_lifetime_years": 3,
                "migration_time_years": 0,
                "threat_horizon_years": 15,
                "exposure": "isolated",
                "migration_effort": "low",
                "risk_reasons": ["No quantum vulnerability"],
                "hybrid_recommended": False,
                "logical_asset_id": "asset-sha-256",
            },
            {
                "scan_job_id": scan_id,
                "algorithm": "DH-1024",
                "category": "key_establishment",
                "source": ["file"],
                "location": "src/keyexchange.py",
                "confidence": 0.55,
                "conflict": False,
                "quantum_vulnerable": True,
                "priority_score": 55,
                "priority_label": "HIGH",
                "pqc_candidate": "Evaluate ML-KEM",
                "business_criticality": "medium",
                "usage": "key_establishment",
                "library": "openssl",
                "protocol": "TLS",
                "key_size": 1024,
                "data_sensitivity": "medium",
                "data_lifetime_years": 5,
                "migration_time_years": 2,
                "threat_horizon_years": 10,
                "exposure": "partner",
                "migration_effort": "medium",
                "risk_reasons": ["DH vulnerable to quantum attacks"],
                "hybrid_recommended": False,
                "logical_asset_id": "asset-dh-1024",
            },
        ]

        with SessionLocal() as db:
            for a in assets:
                db.add(CryptoAssetDB(**a))
            db.commit()

    # ── CycloneDX 1.6 structure ─────────────────────────────────────────────

    def test_cbom_returns_cyclonedx_1_6_structure(self, client: TestClient):
        """GET /api/cbom returns a valid CycloneDX 1.6 document."""
        scan_id = _create_completed_scan(client)
        self._seed_assets(client, scan_id)

        resp = client.get(f"/api/cbom?scan_id={scan_id}")
        assert resp.status_code == 200
        body = resp.json()

        # Top-level CycloneDX keys.
        assert body["$schema"] == "https://cyclonedx.org/schema/bom-1.6.schema.json"
        assert body["bomFormat"] == "CycloneDX"
        assert body["specVersion"] == "1.6"
        assert body["version"] == 1
        assert isinstance(body["metadata"], dict)
        assert isinstance(body["components"], list)
        assert len(body["components"]) == 5

    def test_serial_number_urn_uuid_format(self, client: TestClient):
        """serialNumber follows urn:uuid:<uuid> format."""
        scan_id = _create_completed_scan(client)
        self._seed_assets(client, scan_id)

        resp = client.get(f"/api/cbom?scan_id={scan_id}")
        assert resp.status_code == 200
        serial = resp.json()["serialNumber"]
        assert serial.startswith("urn:uuid:")
        rest = serial[len("urn:uuid:"):]
        # Should be a valid UUID.
        parsed = uuid.UUID(rest)
        assert str(parsed) == rest

    def test_serial_number_deterministic(self, client: TestClient):
        """Same scan_id always produces the same serialNumber."""
        scan_id = _create_completed_scan(client)

        r1 = client.get(f"/api/cbom?scan_id={scan_id}")
        r2 = client.get(f"/api/cbom?scan_id={scan_id}")
        assert r1.json()["serialNumber"] == r2.json()["serialNumber"]

    # ── Component enrichment ─────────────────────────────────────────────────

    def test_components_have_risk_label_property(self, client: TestClient):
        """Each component has an ecdat:risk-label property."""
        scan_id = _create_completed_scan(client)
        self._seed_assets(client, scan_id)

        resp = client.get(f"/api/cbom?scan_id={scan_id}")
        body = resp.json()

        for comp in body["components"]:
            props = {p["name"]: p["value"] for p in comp["properties"]}
            assert "ecdat:risk-label" in props
            assert props["ecdat:risk-label"] in ("CRITICAL", "HIGH", "MEDIUM", "LOW")

    def test_components_have_risk_score_property(self, client: TestClient):
        """Each component has an ecdat:risk-score property (0-100 int)."""
        scan_id = _create_completed_scan(client)
        self._seed_assets(client, scan_id)

        resp = client.get(f"/api/cbom?scan_id={scan_id}")
        body = resp.json()

        for comp in body["components"]:
            props = {p["name"]: p["value"] for p in comp["properties"]}
            assert "ecdat:risk-score" in props
            score = int(props["ecdat:risk-score"])
            assert 0 <= score <= 100

    def test_components_have_quantum_vulnerable_property(self, client: TestClient):
        """Each component has ecdat:quantum-vulnerable boolean property."""
        scan_id = _create_completed_scan(client)
        self._seed_assets(client, scan_id)

        resp = client.get(f"/api/cbom?scan_id={scan_id}")
        body = resp.json()

        for comp in body["components"]:
            props = {p["name"]: p["value"] for p in comp["properties"]}
            assert "ecdat:quantum-vulnerable" in props
            assert props["ecdat:quantum-vulnerable"] in ("true", "false")

    def test_components_have_key_size_property(self, client: TestClient):
        """Each component has ecdat:key-size property when not null."""
        scan_id = _create_completed_scan(client)
        self._seed_assets(client, scan_id)

        resp = client.get(f"/api/cbom?scan_id={scan_id}")
        body = resp.json()

        for comp in body["components"]:
            props = {p["name"]: p["value"] for p in comp["properties"]}
            # key-size is omitted from properties when the DB value is None
            if comp["name"] != "SHA-256":
                assert "ecdat:key-size" in props

    def test_components_have_protocol_property(self, client: TestClient):
        """Each component has ecdat:protocol property."""
        scan_id = _create_completed_scan(client)
        self._seed_assets(client, scan_id)

        resp = client.get(f"/api/cbom?scan_id={scan_id}")
        body = resp.json()

        for comp in body["components"]:
            props = {p["name"]: p["value"] for p in comp["properties"]}
            assert "ecdat:protocol" in props

    def test_components_have_migration_recommendation_property(self, client: TestClient):
        """Each component has ecdat:migration-recommendation property."""
        scan_id = _create_completed_scan(client)
        self._seed_assets(client, scan_id)

        resp = client.get(f"/api/cbom?scan_id={scan_id}")
        body = resp.json()

        for comp in body["components"]:
            props = {p["name"]: p["value"] for p in comp["properties"]}
            assert "ecdat:migration-recommendation" in props
            assert len(props["ecdat:migration-recommendation"]) > 0

    def test_risk_labels_match_source_data(self, client: TestClient):
        """Risk labels in CBOM match the seeded priority_label values."""
        scan_id = _create_completed_scan(client)
        self._seed_assets(client, scan_id)

        resp = client.get(f"/api/cbom?scan_id={scan_id}")
        body = resp.json()
        prop_map = {
            comp["name"]: {p["name"]: p["value"] for p in comp["properties"]}
            for comp in body["components"]
        }

        assert prop_map["RSA-2048"]["ecdat:risk-label"] == "CRITICAL"
        assert prop_map["AES-256"]["ecdat:risk-label"] == "LOW"
        assert prop_map["ECDSA-P256"]["ecdat:risk-label"] == "HIGH"
        assert prop_map["SHA-256"]["ecdat:risk-label"] == "LOW"
        assert prop_map["DH-1024"]["ecdat:risk-label"] == "HIGH"

    def test_risk_scores_match_source_data(self, client: TestClient):
        """Risk scores in CBOM match the seeded priority_score values."""
        scan_id = _create_completed_scan(client)
        self._seed_assets(client, scan_id)

        resp = client.get(f"/api/cbom?scan_id={scan_id}")
        body = resp.json()
        prop_map = {
            comp["name"]: {p["name"]: p["value"] for p in comp["properties"]}
            for comp in body["components"]
        }

        assert int(prop_map["RSA-2048"]["ecdat:risk-score"]) == 80
        assert int(prop_map["AES-256"]["ecdat:risk-score"]) == 10
        assert int(prop_map["ECDSA-P256"]["ecdat:risk-score"]) == 60

    # ── Metadata ─────────────────────────────────────────────────────────────

    def test_metadata_contains_tools_and_properties(self, client: TestClient):
        """CBOM metadata includes ECDAT tool info and scan properties."""
        scan_id = _create_completed_scan(client)
        self._seed_assets(client, scan_id)

        resp = client.get(f"/api/cbom?scan_id={scan_id}")
        body = resp.json()
        meta = body["metadata"]

        assert "tools" in meta
        assert meta["tools"]["components"][0]["name"] == "ECDAT"
        assert "properties" in meta
        prop_names = [p["name"] for p in meta["properties"]]
        assert "ecdat:scan:id" in prop_names
        assert "ecdat:repository:path" in prop_names

    # ── Error handling ────────────────────────────────────────────────────────

    def test_cbom_404_no_completed_scan(self, client: TestClient):
        """GET /api/cbom returns 404 when no completed scan exists."""
        from backend.db import SessionLocal
        with SessionLocal() as db:
            db.query(ScanJobDB).filter(ScanJobDB.status == "completed").delete()
            db.commit()
        resp = client.get("/api/cbom")
        assert resp.status_code == 404

    def test_cbom_404_invalid_scan_id(self, client: TestClient):
        """GET /api/cbom returns 404 for a non-existent scan id."""
        resp = client.get("/api/cbom?scan_id=999999")
        assert resp.status_code == 404

    def test_cbom_409_incomplete_scan(self, client: TestClient):
        """GET /api/cbom returns 409 for a non-completed scan."""
        resp = client.post("/api/scan", json={"repo_path": "/test/repo"})
        scan_id = resp.json()["scan_id"]

        cbom_resp = client.get(f"/api/cbom?scan_id={scan_id}")
        assert cbom_resp.status_code == 409
