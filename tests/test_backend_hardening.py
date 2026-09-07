"""Focused regression tests for backend deployment and API hardening."""
import os
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from pydantic import ValidationError


class ReadinessTests(TestCase):
    def test_readiness_rejects_database_without_application_schema(self):
        from backend.main import readiness

        engine = create_engine("sqlite://")
        session_factory = sessionmaker(bind=engine)
        try:
            with patch("backend.db.SessionLocal", session_factory):
                with self.assertRaises(HTTPException) as error:
                    readiness()
            self.assertEqual(503, error.exception.status_code)
        finally:
            engine.dispose()


class CompletedScanOutputTests(TestCase):
    def test_cbom_rejects_explicit_incomplete_scan(self):
        from backend.db import Base
        from backend.models.scan_job import ScanJobDB
        from backend.routers import outputs

        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine)
        with session_factory() as db:
            job = ScanJobDB(repo_path="fixture", status="running")
            db.add(job)
            db.commit()
            scan_id = job.id
        try:
            with patch.object(outputs, "SessionLocal", session_factory):
                with self.assertRaises(HTTPException) as error:
                    outputs.cbom(scan_id)
            self.assertEqual(409, error.exception.status_code)
        finally:
            engine.dispose()

    def test_output_scan_id_zero_is_rejected_by_api_validation(self):
        from backend.main import app

        with patch.dict(os.environ, {"ECDAT_ALLOW_ROLE_HEADER": "true"}):
            response = TestClient(app).get("/api/cbom?scan_id=0")
        self.assertEqual(422, response.status_code)

    def test_cbom_uses_cyclonedx_standard_extension_fields(self):
        from backend.db import Base
        from backend.models.scan_job import ScanJobDB
        from backend.routers import outputs

        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine)
        with session_factory() as db:
            job = ScanJobDB(repo_path="fixture", status="completed", coverage_pct=100)
            db.add(job)
            db.commit()
            scan_id = job.id
        try:
            with patch.object(outputs, "SessionLocal", session_factory):
                result = outputs.cbom(scan_id)
            self.assertEqual("CycloneDX", result["bomFormat"])
            self.assertEqual("1.6", result["specVersion"])
            self.assertTrue(result["serialNumber"].startswith("urn:uuid:"))
            self.assertNotIn("scan_id", result)
            self.assertIn("properties", result["metadata"])
        finally:
            engine.dispose()


class RiskContextValidationTests(TestCase):
    def test_unknown_risk_context_label_is_rejected(self):
        from backend.schemas.asset import AssetUpdate

        with self.assertRaises(ValidationError):
            AssetUpdate(business_criticality="urgent")


class PaginationValidationTests(TestCase):
    def test_scan_history_rejects_zero_limit(self):
        from backend.main import app

        with patch.dict(os.environ, {"ECDAT_ALLOW_ROLE_HEADER": "true"}):
            response = TestClient(app).get("/api/scans?limit=0")
        self.assertEqual(422, response.status_code)


class MigrationHardeningTests(TestCase):
    def test_baseline_has_one_asset_scan_foreign_key(self):
        project_root = Path(__file__).resolve().parent.parent
        with tempfile.TemporaryDirectory() as directory:
            database_url = f"sqlite:///{Path(directory) / 'migration.db'}"
            config = Config(str(project_root / "alembic.ini"))
            config.config_file_name = None
            config.set_main_option("script_location", str(project_root / "alembic"))
            with patch.dict(os.environ, {"DATABASE_URL": database_url}):
                command.upgrade(config, "69254661dfed")
            engine = create_engine(database_url)
            try:
                keys = inspect(engine).get_foreign_keys("crypto_assets")
                self.assertEqual(1, len(keys))
            finally:
                engine.dispose()

    def test_audit_history_rejects_negative_limit(self):
        from backend.main import app

        with patch.dict(os.environ, {"ECDAT_ALLOW_ROLE_HEADER": "true"}):
            response = TestClient(app).get(
                "/api/audit-logs?limit=-1", headers={"X-ECDAT-Role": "auditor"}
            )
        self.assertEqual(422, response.status_code)
