"""Dependency-light unit and API integration tests for the ECDAT prototype."""
from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path


_TEST_ROOT = Path(tempfile.mkdtemp(prefix="ecdat-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_TEST_ROOT / 'test.db').as_posix()}"

from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402
from backend.db import engine  # noqa: E402
from backend.services.confidence import SOURCE_STRENGTH, score_finding  # noqa: E402
from backend.services.risk_engine import assess_risk  # noqa: E402
from backend.services.repository_guard import resolve_repository  # noqa: E402
from scanner.main import scan_with_metrics  # noqa: E402


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_REPOSITORY = PROJECT_ROOT / "test-repo"


class ConfidenceTests(unittest.TestCase):
    def test_single_source_matches_source_strength(self) -> None:
        for source, strength in SOURCE_STRENGTH.items():
            with self.subTest(source=source):
                self.assertEqual(score_finding({"sources": [source]})["confidence"], strength)

    def test_agreeing_source_bonus_is_capped(self) -> None:
        for count, bonus in ((2, 0.08), (3, 0.16), (4, 0.20), (5, 0.20), (6, 0.20)):
            with self.subTest(count=count):
                sources = list(SOURCE_STRENGTH)[:count]
                result = score_finding({
                    "sources": sources,
                    "confidence_by_source": {source: 0.4 for source in sources},
                })
                self.assertAlmostEqual(result["confidence"], 0.4 + bonus)

    def test_conflict_subtracts_point_two(self) -> None:
        finding = {"sources": ["binary", "dep"]}
        agreeing = score_finding(finding)["confidence"]
        conflicting = score_finding({**finding, "conflict": True})["confidence"]
        self.assertAlmostEqual(conflicting, agreeing - 0.20)

    def test_final_score_is_clamped(self) -> None:
        for strength, conflict, expected in ((0.05, True, 0.0), (1.0, False, 1.0)):
            with self.subTest(expected=expected):
                result = score_finding({
                    "sources": ["binary", "dep"],
                    "confidence_by_source": {"binary": strength, "dep": strength},
                    "conflict": conflict,
                })
                self.assertEqual(result["confidence"], expected)


class RiskEngineTests(unittest.TestCase):
    def test_quantum_signature_recommendation_and_hybrid_transition(self) -> None:
        result = assess_risk({
            "algorithm": "ECDSA",
            "usage": "signature",
            "business_criticality": "critical",
            "data_sensitivity": "critical",
            "data_lifetime_years": 20,
            "migration_time_years": 5,
            "threat_horizon_years": 15,
            "exposure": "internet",
            "migration_effort": "high",
        })
        self.assertTrue(result["quantum_vulnerable"])
        self.assertTrue(result["threat_overlap"])
        self.assertTrue(result["hybrid_recommended"])
        self.assertEqual(result["priority_label"], "CRITICAL")
        self.assertIn("ML-DSA", result["pqc_candidate"])

    def test_symmetric_crypto_is_not_marked_shor_vulnerable(self) -> None:
        result = assess_risk({"algorithm": "AES", "usage": "encryption"})
        self.assertFalse(result["quantum_vulnerable"])
        self.assertIn("AES-256", result["pqc_candidate"])


class ScannerTests(unittest.TestCase):
    def test_controlled_repository_has_measured_full_supported_file_coverage(self) -> None:
        evidence, metrics = scan_with_metrics(str(TEST_REPOSITORY))
        self.assertGreater(sum(len(items) for items in evidence.values()), 0)
        self.assertEqual(metrics["coverage_pct"], 100.0)
        self.assertEqual(metrics["failed_files"], 0)
        self.assertEqual(set(metrics["collector_stats"]), {"ast", "rule", "dep", "cert"})

    def test_scan_root_boundary_can_be_enforced(self) -> None:
        original = os.environ.get("ECDAT_ALLOWED_SCAN_ROOTS")
        try:
            os.environ["ECDAT_ALLOWED_SCAN_ROOTS"] = str(TEST_REPOSITORY.parent)
            self.assertEqual(Path(resolve_repository(str(TEST_REPOSITORY))), TEST_REPOSITORY.resolve())
            os.environ["ECDAT_ALLOWED_SCAN_ROOTS"] = str(_TEST_ROOT)
            with self.assertRaises(Exception) as context:
                resolve_repository(str(TEST_REPOSITORY))
            self.assertEqual(getattr(context.exception, "status_code", None), 403)
        finally:
            if original is None:
                os.environ.pop("ECDAT_ALLOWED_SCAN_ROOTS", None)
            else:
                os.environ["ECDAT_ALLOWED_SCAN_ROOTS"] = original


class ApiIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client_context = TestClient(app)
        cls.client = cls.client_context.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client_context.__exit__(None, None, None)

    def test_end_to_end_scan_outputs_rbac_and_latest_snapshot(self) -> None:
        self.assertEqual(self.client.get("/health").status_code, 200)
        self.assertEqual(self.client.get("/ready").json()["status"], "ready")

        self.assertEqual(
            self.client.post("/api/auth/login", json={"username": "analyst", "password": "wrong"}).status_code,
            401,
        )
        login = self.client.post(
            "/api/auth/login", json={"username": "analyst", "password": "ecdat-demo"},
        )
        self.assertEqual(login.status_code, 200)
        token = login.json()["access_token"]
        self.assertEqual(
            self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["role"],
            "security_analyst",
        )

        denied = self.client.post(
            "/api/scan", json={"repo_path": "/test-repo"},
            headers={"X-ECDAT-Role": "viewer"},
        )
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(self.client.post("/api/scan", json={"repo_path": "Z:/missing"}).status_code, 400)

        first = self.client.post(
            "/api/scan", json={"repo_path": "/test-repo"},
            headers={"X-ECDAT-Role": "security_analyst"},
        )
        self.assertEqual(first.status_code, 200)
        first_id = first.json()["scan_id"]
        self.assertEqual(self.client.get(f"/api/scans/{first_id}").json()["status"], "completed")

        assets = self.client.get("/api/assets").json()
        summary = self.client.get("/api/dashboard/summary").json()
        self.assertEqual(len(assets), 15)
        self.assertEqual(summary["total_assets"], 15)
        self.assertEqual(summary["coverage_pct"], 100.0)
        self.assertEqual(summary["quantum_vulnerable_count"], 7)
        self.assertEqual(summary["conflict_count"], 2)

        evaluation = self.client.get("/api/evaluation").json()
        self.assertEqual(evaluation["precision"], 1.0)
        self.assertEqual(evaluation["recall"], 1.0)
        self.assertEqual(evaluation["f1"], 1.0)
        self.assertEqual(len(self.client.get("/api/cbom").json()["components"]), 15)
        self.assertEqual(len(self.client.get("/api/reports/risk").json()["migration_priorities"]), 15)
        graph = self.client.get("/api/evidence-graph").json()
        self.assertGreater(len(graph["nodes"]), 15)
        self.assertGreater(len(graph["edges"]), 0)
        self.assertEqual(self.client.get("/api/reports/risk.txt").status_code, 200)

        rsa = next(asset for asset in assets if asset["algorithm"] == "RSA")
        updated = self.client.patch(
            f"/api/assets/{rsa['id']}",
            json={
                "business_criticality": "critical",
                "data_sensitivity": "critical",
                "data_lifetime_years": 20,
                "migration_time_years": 5,
                "exposure": "internet",
                "migration_effort": "high",
            },
            headers={"X-ECDAT-Role": "security_analyst"},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["priority_label"], "CRITICAL")
        self.assertTrue(updated.json()["hybrid_recommended"])

        self.assertEqual(
            self.client.get("/api/audit-logs", headers={"X-ECDAT-Role": "viewer"}).status_code,
            403,
        )
        audit = self.client.get("/api/audit-logs", headers={"X-ECDAT-Role": "auditor"})
        self.assertEqual(audit.status_code, 200)
        self.assertGreaterEqual(len(audit.json()), 2)

        second = self.client.post(
            "/api/scan", json={"repo_path": "/test-repo"},
            headers={"X-ECDAT-Role": "security_analyst"},
        )
        second_id = second.json()["scan_id"]
        latest_summary = self.client.get("/api/dashboard/summary").json()
        self.assertEqual(latest_summary["latest_scan_id"], second_id)
        self.assertEqual(latest_summary["total_assets"], 15)
        self.assertEqual(len(self.client.get("/api/assets").json()), 15)
        self.assertEqual(len(self.client.get(f"/api/assets?scan_job_id={first_id}").json()), 15)
        self.assertEqual(self.client.get("/api/assets/999999").status_code, 404)


def tearDownModule() -> None:
    engine.dispose()
    shutil.rmtree(_TEST_ROOT, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
