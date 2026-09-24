"""Dependency-light unit and API integration tests for the ECDAT prototype."""
# ruff: noqa: I001
from __future__ import annotations

import json
import os
import secrets
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.integration_env import PASSWORD as _TEST_PASSWORD
from tests.integration_env import ROOT as _TEST_ROOT

from fastapi.testclient import TestClient

from backend.db import engine
from backend.main import app
from backend.services.confidence import (
    EVIDENCE_KIND_STRENGTH,
    score_finding,
)
from backend.services.repository_guard import resolve_repository
from backend.services.risk_engine import assess_risk
from backend.services.scanner_runner import _finding_provenance
from scanner.main import scan_with_metrics
PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_REPOSITORY = PROJECT_ROOT / "test-repo"


class ConfidenceTests(unittest.TestCase):
    def test_finding_provenance_preserves_collector_metadata(self) -> None:
        finding = {
            "evidence_list": [{
                "parser_version": "ast-v3",
                "confidence_reasons": [{"source": "ast", "note": "resolved call"}],
            }],
        }

        parser_version, reasons = _finding_provenance(finding)

        self.assertEqual(parser_version, "ast-v3")
        self.assertEqual(reasons, [{"source": "ast", "note": "resolved call"}])

    def test_single_evidence_kind_scores_correctly(self) -> None:
        for kind, strength in EVIDENCE_KIND_STRENGTH.items():
            with self.subTest(evidence_kind=kind):
                self.assertEqual(
                    score_finding({"evidence_list": [{"evidence": {"evidence_kind": kind}}]})["confidence"],
                    strength,
                )

    def test_agreeing_evidence_kind_bonus_is_capped(self) -> None:
        for count, expected_bonus in ((2, 0.08), (3, 0.16), (4, 0.20), (5, 0.20), (6, 0.20)):
            with self.subTest(count=count):
                kinds = list(EVIDENCE_KIND_STRENGTH)[:count]
                strengths = [EVIDENCE_KIND_STRENGTH[k] for k in kinds]
                avg = sum(strengths) / len(strengths)
                bonus = min(0.20, 0.08 * max(0, count - 1))
                expected = min(1.0, round(avg + bonus, 4))
                result = score_finding({
                    "evidence_list": [{"evidence": {"evidence_kind": kind}} for kind in kinds],
                })
                self.assertAlmostEqual(result["confidence"], expected)

    def test_conflict_subtracts_point_two(self) -> None:
        agreeing = score_finding({
            "evidence_list": [
                {"evidence": {"evidence_kind": "observed_operation"}},
                {"evidence": {"evidence_kind": "configured_protocol"}},
            ],
        })["confidence"]
        conflicting = score_finding({
            "evidence_list": [
                {"evidence": {"evidence_kind": "observed_operation"}},
                {"evidence": {"evidence_kind": "configured_protocol"}},
            ],
            "conflict": True,
        })["confidence"]
        self.assertAlmostEqual(conflicting, agreeing - 0.20)

    def test_final_score_is_clamped(self) -> None:
        # Max possible with all 5 evidence kinds: avg(0.90+0.85+0.65+0.50+0.30) + 0.20 = 0.84
        all_kinds = list(EVIDENCE_KIND_STRENGTH.keys())
        result = score_finding({
            "evidence_list": [{"evidence": {"evidence_kind": kind}} for kind in all_kinds],
        })
        self.assertEqual(result["confidence"], 0.84)
        # Single high-confidence kind
        single = score_finding({
            "evidence_list": [{"evidence": {"evidence_kind": "observed_operation"}}],
        })
        self.assertAlmostEqual(single["confidence"], 0.90)
        # Conflict subtracts 0.20 from the score before clamping
        no_conflict_unknown = score_finding({
            "evidence_list": [{"evidence": {"evidence_kind": "unknown"}}],
        })
        with_conflict_unknown = score_finding({
            "evidence_list": [{"evidence": {"evidence_kind": "unknown"}}],
            "conflict": True,
        })
        self.assertAlmostEqual(with_conflict_unknown["confidence"], no_conflict_unknown["confidence"] - 0.20)
        self.assertAlmostEqual(with_conflict_unknown["confidence"], 0.10)  # 0.30 - 0.20
        # Low score with conflict stays above floor
        with_conflict_artifact = score_finding({
            "evidence_list": [{"evidence": {"evidence_kind": "artifact_metadata"}}],
            "conflict": True,
        })
        self.assertAlmostEqual(with_conflict_artifact["confidence"], 0.30)  # 0.50 - 0.20


class RiskEngineTests(unittest.TestCase):
    def test_confirmed_use_carries_higher_penalty_than_capability_only(self) -> None:
        confirmed = assess_risk({"algorithm": "RSA", "usage": "encryption", "evidence_kind": "observed_operation"})
        capability = assess_risk({"algorithm": "RSA", "usage": "encryption", "evidence_kind": "declared_capability"})
        self.assertGreater(confirmed["priority_score"], capability["priority_score"])
        self.assertTrue(confirmed["confirmed_use"])
        self.assertFalse(confirmed["capability_only"])
        self.assertFalse(capability["confirmed_use"])
        self.assertTrue(capability["capability_only"])

    def test_evidence_kind_returns_vulnerability_note(self) -> None:
        for kind, label in (("observed_operation", "confirmed use of"),
                            ("configured_protocol", "confirmed use of"),
                            ("declared_capability", "capability-only exposure to"),
                            ("artifact_metadata", "capability-only exposure to"),
                            ("unknown", "evidence of")):
            with self.subTest(kind=kind):
                result = assess_risk({"algorithm": "ECDSA", "usage": "signature", "evidence_kind": kind})
                self.assertIn(label, result["risk_reasons"][0])

    def test_deprecated_hashes_require_replacement_without_pqc_hybrid(self) -> None:
        for algorithm in ("SHA-1", "MD5"):
            for effort in ("low", "medium", "high", "critical"):
                with self.subTest(algorithm=algorithm, effort=effort):
                    result = assess_risk({
                        "algorithm": algorithm, "usage": "hash",
                        "migration_effort": effort,
                    })
                    self.assertEqual(
                        result["pqc_candidate"],
                        "Replace deprecated hash with SHA-256 or SHA-3 independent of quantum migration",
                    )
                    self.assertFalse(result["hybrid_recommended"])
                    self.assertFalse(result["quantum_vulnerable"])

    def test_other_hash_recommendations_remain_unchanged(self) -> None:
        for algorithm in ("SHA-256", "SHA-384", "SHA-512", "SHA-3", "BLAKE2", "hash"):
            with self.subTest(algorithm=algorithm):
                result = assess_risk({
                    "algorithm": algorithm, "usage": "hash", "migration_effort": "high",
                })
                self.assertEqual(
                    result["pqc_candidate"],
                    "Use SHA-256/SHA-3 with adequate output length; no public-key migration required",
                )
                self.assertFalse(result["hybrid_recommended"])
                self.assertFalse(result["quantum_vulnerable"])

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
    def test_progress_preserves_controlled_evidence(self):
        updates = []
        evidence, metrics = scan_with_metrics(str(TEST_REPOSITORY), updates.append)
        self.assertEqual(sum(map(len, evidence.values())), 79)
        self.assertEqual(updates[0]["_files_processed"], 0)
        self.assertEqual(updates[-1]["_files_processed"], metrics["in_scope_files"])
        self.assertEqual(updates[-1]["_files_total"], metrics["in_scope_files"])
        self.assertNotIn("_files_processed", metrics["collector_stats"])

    def test_shared_scope_keeps_site_packages_and_includes_cer(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for folder in ("site-packages", "node_modules"):
                (root / folder).mkdir()
                (root / folder / "crypto.py").write_text("import hashlib\nhashlib.md5(b'x')\n")
            (root / "example.cer").write_bytes(b"not a certificate")
            evidence, metrics = scan_with_metrics(directory)
            self.assertEqual(metrics["in_scope_files"], 2)
            self.assertTrue(evidence)
            self.assertTrue(all("site-packages" in key[1] for key in evidence))

    def test_empty_directory_reports_zero_work(self):
        with tempfile.TemporaryDirectory() as directory:
            updates = []
            evidence, metrics = scan_with_metrics(directory, updates.append)
            self.assertEqual(evidence, {})
            self.assertEqual(updates[-1]["_files_total"], 0)
            self.assertEqual(metrics["in_scope_files"], 0)
            self.assertEqual(metrics["coverage_pct"], 0.0)

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

    def test_request_id_rejects_unbounded_client_value(self):
        response = self.client.get("/health", headers={"X-Request-ID": "x" * 1024})

        self.assertLessEqual(len(response.headers["X-Request-ID"]), 128)

    def test_dashboard_scan_filter_rejects_incomplete_snapshots(self):
        from backend.db import SessionLocal
        from backend.models.scan_job import ScanJobDB

        with SessionLocal() as db:
            job = ScanJobDB(repo_path="dashboard-filter-fixture", status="running")
            db.add(job)
            db.commit()
            scan_id = job.id

        try:
            response = self.client.get(f"/api/dashboard/summary?scan_id={scan_id}")
            self.assertEqual(response.status_code, 200)
            self.assertIsNone(response.json()["latest_scan_id"])
        finally:
            with SessionLocal() as db:
                db.query(ScanJobDB).filter(ScanJobDB.id == scan_id).delete()
                db.commit()

    def test_asset_server_side_filters_sorting_and_pagination(self):
        from backend.db import SessionLocal
        from backend.models.asset import CryptoAssetDB
        from backend.models.scan_job import ScanJobDB

        with SessionLocal() as db:
            job = ScanJobDB(repo_path="filter-fixture", status="completed")
            db.add(job)
            db.flush()
            scan_id = job.id
            fixtures = [
                ("RSA", "encryption", "src/rsa.py", "OpenSSL", 0.95, True, 95, "CRITICAL"),
                ("AES", "encryption", "src/aes.py", "cryptography", 0.90, False, 20, "LOW"),
                ("SHA-1", "hash", "src/legacy_hash.py", "", 0.70, False, 75, "HIGH"),
                ("ECDSA", "signature", "src/sign.py", "OpenSSL", 0.85, True, 85, "HIGH"),
                ("ML-KEM", "encryption", "src/pqc.py", "liboqs", 0.99, False, 10, "LOW"),
            ]
            for algorithm, category, location, library, confidence, quantum, score, label in fixtures:
                db.add(CryptoAssetDB(
                    scan_job_id=scan_id,
                    algorithm=algorithm,
                    category=category,
                    location=location,
                    library=library,
                    confidence=confidence,
                    quantum_vulnerable=quantum,
                    priority_score=score,
                    priority_label=label,
                    evidence_kind="observed_operation",
                    parser_version="test-v1",
                    confirmed_use=True,
                    capability_only=False,
                    span={"file": location, "line_start": 1, "line_end": 1},
                ))
            db.commit()

        try:
            base = f"/api/assets?scan_job_id={scan_id}"
            unpaginated = self.client.get(base)
            self.assertEqual(unpaginated.status_code, 200)
            self.assertEqual(len(unpaginated.json()["items"]), 5)
            self.assertEqual(unpaginated.headers["X-Total-Count"], "5")
            cors = self.client.get(base, headers={"Origin": "http://localhost:3000"})
            self.assertIn("X-Total-Count", cors.headers["Access-Control-Expose-Headers"])

            page = self.client.get(base + "&limit=2&offset=1&sort=priority")
            self.assertEqual([item["algorithm"] for item in page.json()["items"]], ["ECDSA", "SHA-1"])
            self.assertEqual(page.headers["X-Total-Count"], "5")

            searched = self.client.get(base + "&q=openssl&sort=algorithm")
            self.assertEqual([item["algorithm"] for item in searched.json()["items"]], ["ECDSA", "RSA"])
            self.assertEqual(searched.headers["X-Total-Count"], "2")

            filtered = self.client.get(base + "&risk=HIGH&quantum=true&sort=confidence")
            self.assertEqual([item["algorithm"] for item in filtered.json()["items"]], ["ECDSA"])
            self.assertEqual(filtered.headers["X-Total-Count"], "1")

            non_quantum = self.client.get(base + "&quantum=false")
            self.assertEqual(len(non_quantum.json()["items"]), 3)
            for query in ("limit=0", "limit=201", "offset=-1", "scan_job_id=0",
                          "risk=URGENT", "sort=unknown", "q=", "q=%20%20"):
                with self.subTest(query=query):
                    self.assertEqual(self.client.get(base + "&" + query).status_code, 422)
        finally:
            with SessionLocal() as db:
                db.query(CryptoAssetDB).filter(CryptoAssetDB.scan_job_id == scan_id).delete()
                db.query(ScanJobDB).filter(ScanJobDB.id == scan_id).delete()
                db.commit()

    def test_pipeline_failures_terminate_jobs_without_leaking_details(self):
        from backend.services.scanner_runner import run_scan
        for stage in ("scan_with_metrics", "correlate", "assess_risk"):
            with self.subTest(stage=stage):
                with patch(f"backend.services.scanner_runner.{stage}",
                           side_effect=RuntimeError("secret-error-canary")):
                    result = run_scan(str(TEST_REPOSITORY))
                self.assertEqual(result["status"], "failed")
                response = self.client.get(f"/api/scans/{result['scan_id']}")
                job = response.json()
                self.assertEqual(job["status"], "failed")
                self.assertIsNotNone(job["finished_at"])
                self.assertNotIn("secret-error-canary", response.text)
                self.assertIn("RuntimeError", str(job["blind_spots"]))

    def test_progress_is_persisted_while_running(self):
        from backend.db import SessionLocal
        from backend.models.scan_job import ScanJobDB
        from backend.services.scanner_runner import run_scan
        with SessionLocal() as db:
            job = ScanJobDB(repo_path=str(TEST_REPOSITORY), status="queued")
            db.add(job)
            db.commit()
            scan_id = job.id

        def scanner(path, progress_callback):
            progress_callback({"_files_processed": 2, "_files_total": 10})
            response = self.client.get(f"/api/scans/{scan_id}").json()
            self.assertEqual(response["status"], "running")
            self.assertEqual(response["collector_stats"]["_files_processed"], 2)
            return scan_with_metrics(path)

        with patch("backend.services.scanner_runner.scan_with_metrics", side_effect=scanner):
            self.assertEqual(run_scan(str(TEST_REPOSITORY), scan_id)["status"], "completed")
        job = self.client.get(f"/api/scans/{scan_id}").json()
        self.assertNotIn("_files_processed", job["collector_stats"])

    def test_secure_authentication_and_validation(self):
        with patch.dict(os.environ, {"ECDAT_ALLOW_ROLE_HEADER": "false"}):
            for value in (123, [], "", "x" * 1025, "\ud800"):
                response = self.client.post("/api/auth/login", content=json.dumps(
                    {"username": "analyst", "password": value}),
                    headers={"Content-Type": "application/json"})
                self.assertEqual(response.status_code, 422)
            endpoints = ["/api/assets", "/api/assets/1", "/api/scans", "/api/scans/1",
                         "/api/dashboard/summary", "/api/cbom", "/api/reports/risk",
                         "/api/reports/risk.txt", "/api/evidence-graph", "/api/evaluation", "/api/audit-logs"]
            for endpoint in endpoints:
                with self.subTest(endpoint=endpoint):
                    self.assertEqual(self.client.get(endpoint).status_code, 401)
                    self.assertEqual(self.client.get(endpoint, headers={"X-ECDAT-Role": "admin"}).status_code, 401)
            self.assertEqual(self.client.post("/api/scan", json={"repo_path": "/test-repo"}).status_code, 401)
            self.assertEqual(self.client.post("/api/auth/login", json={"username": "analyst", "password": "é"}).status_code, 401)
            login = self.client.post("/api/auth/login", json={"username": "analyst", "password": _TEST_PASSWORD})
            self.assertEqual(login.status_code, 200)
            headers = {"Authorization": "Bearer " + login.json()["access_token"]}
            self.assertEqual(self.client.get("/api/assets", headers=headers).status_code, 200)
            bad_headers = {"Authorization": headers["Authorization"] + "x"}
            self.assertEqual(self.client.get("/api/assets", headers=bad_headers).status_code, 401)
            self.assertEqual(self.client.get("/api/audit-logs", headers=headers).status_code, 403)
            for value in (123, ["x"], {"path": "x"}, ""):
                self.assertEqual(self.client.post("/api/scan", json={"repo_path": value}, headers=headers).status_code, 422)
            with patch.dict(os.environ, {"ECDAT_TOKEN_SECRET": ""}):
                self.assertEqual(self.client.post("/api/auth/login", json={"username": "analyst", "password": _TEST_PASSWORD}).status_code, 503)

    def test_secure_defaults_and_viewer_cannot_write(self):
        from fastapi import HTTPException

        from backend.security import current_role, issue_demo_token
        with patch.dict(os.environ):
            os.environ.pop("ECDAT_ALLOW_ROLE_HEADER", None)
            with self.assertRaises(HTTPException) as error:
                current_role(authorization=None, x_ecdat_role="admin")
            self.assertEqual(error.exception.status_code, 401)
            password = secrets.token_urlsafe(24)
            os.environ["ECDAT_USERS_JSON"] = json.dumps({"viewer": {"role": "viewer", "password": password}})
            token = issue_demo_token("viewer", password)["access_token"]
            headers = {"Authorization": "Bearer " + token}
            self.assertEqual(self.client.get("/api/assets", headers=headers).status_code, 200)
            self.assertEqual(self.client.post("/api/scan", headers=headers, json={"repo_path": "/test-repo"}).status_code, 403)
            self.assertEqual(self.client.patch("/api/assets/1", headers=headers, json={"exposure": "internet"}).status_code, 403)
            with patch("backend.security.time.time", return_value=10**12):
                self.assertEqual(self.client.get("/api/assets", headers=headers).status_code, 401)

    def test_redaction_and_mixed_key_sizes(self):
        from backend.services.correlator import correlate
        from scanner.redaction import redact_evidence
        safe = redact_evidence({"snippet": 'AES.new(key); password="canary"', "raw_line": "private", "line": 5})
        self.assertEqual(safe, {"snippet": "[REDACTED]", "raw_line": "[REDACTED]", "line": 5})
        from backend.schemas.asset import AssetResponse
        self.assertEqual(AssetResponse.sanitize_evidence({"snippet": "legacy-secret"}), {"snippet": "[REDACTED]"})
        record = {"algorithm": "RSA", "source": "rule", "location": "a.py", "confidence": 0.8,
                  "evidence": {"usage": "signature", "operation_id": "one", "key_size": 2048}}
        result = correlate({"r": [record, {**record, "evidence": {**record["evidence"], "key_size": "2048"}}]})
        self.assertIsNone(result[0]["key_size"])
        self.assertTrue(result[0]["conflict"])

    def test_operation_context_survives_persistence_and_reports(self) -> None:
        records = [{"algorithm": "RSA", "category": "encryption", "source": "rule",
                    "location": "test-repo/mixed/a.py", "confidence": 0.82,
                    "evidence": {"usage": usage, "operation_id": "same-anchor"}}
                   for usage in ("signature", "encryption", "unknown")]
        metrics = {"total_files": 1, "in_scope_files": 1, "scanned_files": 1,
                   "failed_files": 0, "coverage_pct": 100.0, "duration_ms": 1,
                   "collector_stats": {"rule": 3}, "blind_spots": []}
        with patch("backend.services.scanner_runner.scan_with_metrics", return_value=({"mixed": records}, metrics)):
            from backend.services.scanner_runner import run_scan
            scan_id = run_scan(str(TEST_REPOSITORY))["scan_id"]
        assets = self.client.get(f"/api/assets?scan_job_id={scan_id}").json()["items"]
        self.assertEqual(len(assets), 3)
        self.assertEqual({a["usage"] for a in assets}, {"signature", "encryption", "unknown"})
        priorities = self.client.get(f"/api/reports/risk?scan_id={scan_id}").json()["migration_priorities"]
        self.assertEqual(len(priorities), 3)
        for item in priorities:
            self.assertEqual(item["operation_anchor"], "id:same-anchor")
            if item["usage"] == "signature":
                self.assertIn("ML-DSA", item["recommendation"])
            elif item["usage"] == "unknown":
                self.assertNotIn("ML-KEM", item["recommendation"])
        cbom = self.client.get(f"/api/cbom?scan_id={scan_id}").json()["components"]
        usages = {
            next(p["value"] for p in component["properties"] if p["name"] == "ecdat:usage")
            for component in cbom
        }
        self.assertEqual(usages, {"signature", "encryption", "unknown"})

    def test_end_to_end_scan_outputs_rbac_and_latest_snapshot(self) -> None:
        self.assertEqual(self.client.get("/health").status_code, 200)
        self.assertEqual(self.client.get("/ready").json()["status"], "ready")

        self.assertEqual(
            self.client.post("/api/auth/login", json={"username": "analyst", "password": "wrong"}).status_code,
            401,
        )
        login = self.client.post(
            "/api/auth/login", json={"username": "analyst", "password": _TEST_PASSWORD},
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

        assets = self.client.get("/api/assets?limit=200").json()["items"]
        summary = self.client.get("/api/dashboard/summary").json()
        # Operation-v2 retains operation-level findings while removing broad
        # package capabilities contradicted by stronger source evidence.
        self.assertEqual(len({a["logical_asset_id"] for a in assets}), 68)
        self.assertTrue(all(a["evidence_json"]["correlation_version"] == "operation-v2" for a in assets))
        self.assertEqual(summary["total_assets"], 68)
        self.assertEqual(summary["coverage_pct"], 100.0)
        self.assertEqual(summary["quantum_vulnerable_count"], 31)
        self.assertEqual(summary["conflict_count"], 2)

        evaluation = self.client.get("/api/evaluation").json()
        self.assertEqual(evaluation["precision"], 1.0)
        self.assertEqual(evaluation["recall"], 1.0)
        self.assertEqual(evaluation["f1"], 1.0)
        self.assertEqual(evaluation["granularity"], "component_algorithm")
        self.assertEqual(evaluation["found"], 17)
        self.assertEqual(evaluation["operation_findings"], 68)
        components = self.client.get("/api/cbom").json()["components"]
        priorities = self.client.get("/api/reports/risk").json()["migration_priorities"]
        self.assertEqual(len(components), 68)
        self.assertEqual(len(priorities), 68)
        by_id = {a["logical_asset_id"]: a for a in assets}
        for item in priorities:
            original = by_id[item["logical_asset_id"]]
            self.assertEqual(item["usage"], original["usage"])
            self.assertEqual(item["operation_anchor"], original["evidence_json"]["operation_anchor"])
        graph = self.client.get("/api/evidence-graph").json()
        self.assertGreater(len(graph["nodes"]), 15)
        self.assertGreater(len(graph["edges"]), 0)
        self.assertEqual(self.client.get("/api/reports/risk.txt").status_code, 200)

        rsa = next(asset for asset in assets if asset["algorithm"] == "RSA" and asset["evidence_json"].get("evidence_kind") == "observed_operation")
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
        self.assertEqual(latest_summary["total_assets"], 68)
        latest_assets = self.client.get("/api/assets?limit=200").json()["items"]
        self.assertEqual(len(latest_assets), summary["total_assets"])
        self.assertEqual({a["logical_asset_id"] for a in latest_assets}, set(by_id))
        self.assertEqual(self.client.get(f"/api/assets?scan_job_id={first_id}&limit=200").json()["total"], summary["total_assets"])
        self.assertEqual(self.client.get("/api/assets/999999").status_code, 404)


def tearDownModule() -> None:
    engine.dispose()


if __name__ == "__main__":
    unittest.main(verbosity=2)
