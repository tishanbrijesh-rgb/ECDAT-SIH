import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db import Base
from backend.models.scan_job import ScanJobDB
from backend.routers import scan as scan_router
from backend.routers import outputs as outputs_router
from backend.schemas.asset import ScanJobResponse
from backend.security import current_role
from backend.services import scanner_runner
from scanner.main import scan_with_metrics


class ScanFailureMetricTests(unittest.TestCase):
    def test_oversized_failure_is_relative_and_sanitized(self):
        with tempfile.TemporaryDirectory() as directory:
            nested = Path(directory) / "nested"
            nested.mkdir()
            (nested / "large.py").write_text("x = 1\n" + " " * 200)

            with patch.dict(os.environ, {"ECDAT_MAX_FILE_BYTES": "64"}):
                _, metrics = scan_with_metrics(directory)

            self.assertEqual(
                metrics["failures"],
                [{"path": "nested/large.py", "reason": "oversized"}],
            )
            self.assertNotIn(directory, str(metrics["failures"]))

    def test_parser_failure_uses_fixed_code_without_exception_text(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "broken.py").write_text("def invalid(:\n")

            _, metrics = scan_with_metrics(directory)

            self.assertEqual(
                metrics["failures"],
                [{"path": "broken.py", "reason": "parse_error"}],
            )

    def test_invalid_certificate_uses_certificate_error_code(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "broken.pem").write_text("not a certificate")

            _, metrics = scan_with_metrics(directory)

            self.assertEqual(
                metrics["failures"],
                [{"path": "broken.pem", "reason": "certificate_error"}],
            )


class ScanFailureApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        database = Path(self.temp.name) / "failures.db"
        self.engine = create_engine("sqlite:///" + database.as_posix())
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.runner_session = patch.object(scanner_runner, "SessionLocal", self.Session)
        self.router_session = patch.object(scan_router, "SessionLocal", self.Session)
        self.outputs_session = patch.object(outputs_router, "SessionLocal", self.Session)
        self.runner_session.start()
        self.router_session.start()
        self.outputs_session.start()

        app = FastAPI()
        app.include_router(scan_router.router, dependencies=[Depends(current_role)])
        app.include_router(outputs_router.router, dependencies=[Depends(current_role)])
        app.dependency_overrides[current_role] = lambda: "viewer"
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()

    def tearDown(self):
        self.client_context.__exit__(None, None, None)
        self.router_session.stop()
        self.outputs_session.stop()
        self.runner_session.stop()
        self.engine.dispose()
        self.temp.cleanup()

    def test_runner_persists_details_and_api_hides_internal_envelope(self):
        repo = str(Path(self.temp.name) / "private-root")
        metrics = {
            "total_files": 1,
            "in_scope_files": 1,
            "scanned_files": 0,
            "failed_files": 1,
            "coverage_pct": 0.0,
            "duration_ms": 1,
            "collector_stats": {"ast": 0, "rule": 0, "dep": 0, "cert": 0},
            "blind_spots": ["Evidence may be partial"],
            "failures": [
                {"path": "src/broken.py", "reason": "parse_error"}
            ],
        }
        with patch.object(scanner_runner, "scan_with_metrics", return_value=({}, metrics)):
            result = scanner_runner.run_scan(repo)

        response = self.client.get(f"/api/scans/{result['scan_id']}")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["failures"], metrics["failures"])
        self.assertEqual(body["blind_spots"], ["Evidence may be partial"])
        self.assertNotIn("__failed_file__", response.text)
        listed = self.client.get("/api/scans").json()
        self.assertEqual(listed[0]["failures"], metrics["failures"])
        self.assertNotIn("__failed_file__", str(listed))
        risk_report = self.client.get(f"/api/reports/risk?scan_id={result['scan_id']}").json()
        self.assertEqual(risk_report["blind_spots"], ["Evidence may be partial"])
        self.assertNotIn("__failed_file__", str(risk_report))

    def test_schema_rejects_unsafe_persisted_failure_records(self):
        job = ScanJobDB(
            id=1,
            repo_path="C:/private/repo",
            status="completed",
            assets_found=0,
            total_files=0,
            in_scope_files=0,
            scanned_files=0,
            failed_files=0,
            coverage_pct=0.0,
            duration_ms=0,
            collector_stats={},
            blind_spots=[
                '__failed_file__:{"path":"../secret.py","reason":"parse_error"}',
                '__failed_file__:{"path":"safe.py","reason":"raw secret"}',
            ],
        )
        response = ScanJobResponse.model_validate(job)
        self.assertEqual(response.failures, [])
        self.assertEqual(response.blind_spots, [])


if __name__ == "__main__":
    unittest.main()
