"""End-to-end tests for Alembic migrations.

Uses an isolated SQLite file per test method (in a temp directory) so tests
never touch the shared test database.  Migrations run programmatically via
alembic.command with DATABASE_URL env var.
"""
import os
import tempfile
import unittest
from pathlib import Path

from alembic.config import Config
from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text, pool

PROJECT_ROOT = Path(__file__).resolve().parent.parent

ALEMBIC_CFG = str(PROJECT_ROOT / "alembic.ini")
ALEMBIC_DIR = str((PROJECT_ROOT / "alembic").resolve())


def _make_config(db_url: str) -> Config:
    """Build an Alembic Config for the given database URL."""
    os.environ["DATABASE_URL"] = db_url
    cfg = Config(ALEMBIC_CFG)
    cfg.config_file_name = None
    cfg.set_main_option("script_location", ALEMBIC_DIR)
    return cfg


class TestMigrations(unittest.TestCase):
    """Migration lifecycle tests against a throwaway SQLite file."""

    def setUp(self):
        self._original_database_url = os.environ.get("DATABASE_URL")
        # Fresh DB file for every test method
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_url = f"sqlite:///{Path(self._tmpdir.name) / 'ecdat_test.db'}"
        # NullPool so file handles are released on dispose()
        self._engine = create_engine(self.db_url, poolclass=pool.NullPool)

    def tearDown(self):
        # Release SQLite file handle before cleanup
        self._engine.dispose()
        # Small delay to let OS release the lock on Windows
        import gc
        gc.collect()
        self._tmpdir.cleanup()
        if self._original_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = self._original_database_url

    def _inspect(self):
        return inspect(self._engine)

    def _upgrade(self, revision: str):
        command.upgrade(_make_config(self.db_url), revision)

    def _downgrade(self, revision: str):
        command.downgrade(_make_config(self.db_url), revision)

    # ── baseline ────────────────────────────────────────────────────────────

    def test_0001_creates_three_tables(self):
        """Upgrading from base creates scan_jobs, crypto_assets, audit_logs."""
        self._upgrade("69254661dfed")
        insp = self._inspect()
        for expected in ("scan_jobs", "crypto_assets", "audit_logs"):
            self.assertIn(expected, insp.get_table_names(),
                          f"{expected} table missing after 0001")

    def test_0001_columns_match_models(self):
        """Each column in the baseline tables matches the SQLAlchemy model."""
        self._upgrade("69254661dfed")
        insp = self._inspect()

        expected_scan_job_cols = {
            "id", "repo_path", "started_at", "finished_at", "status",
            "assets_found", "avg_confidence", "total_files", "in_scope_files",
            "scanned_files", "failed_files", "coverage_pct", "duration_ms",
            "collector_stats", "blind_spots",
        }
        actual = {c["name"] for c in insp.get_columns("scan_jobs")}
        self.assertEqual(expected_scan_job_cols, actual)

        expected_asset_cols = {
            "id", "scan_job_id", "algorithm", "category", "source",
            "location", "evidence_json", "confidence", "conflict",
            "quantum_vulnerable", "priority_score", "priority_label",
            "pqc_candidate", "business_criticality", "usage", "library",
            "protocol", "key_size", "data_sensitivity", "data_lifetime_years",
            "migration_time_years", "threat_horizon_years", "exposure",
            "migration_effort", "risk_reasons", "hybrid_recommended",
            "logical_asset_id", "created_at",
        }
        actual = {c["name"] for c in insp.get_columns("crypto_assets")}
        self.assertEqual(expected_asset_cols, actual)

    # ── 0002 scan_failures ──────────────────────────────────────────────────

    def test_0002_adds_scan_failures_table(self):
        """Migration 0002 creates the scan_failures table with correct columns."""
        self._upgrade("a7f3c2e91d04")
        insp = self._inspect()
        self.assertIn("scan_failures", insp.get_table_names())
        cols = {c["name"] for c in insp.get_columns("scan_failures")}
        self.assertEqual({"id", "scan_job_id", "path", "reason", "created_at"}, cols)

        fks = insp.get_foreign_keys("scan_failures")
        self.assertEqual(1, len(fks))
        self.assertEqual("scan_jobs", fks[0]["referred_table"])

    # ── downgrade ───────────────────────────────────────────────────────────

    def test_downgrade_removes_scan_failures(self):
        """Downgrading -2 removes scan_failures but keeps the other tables."""
        self._upgrade("head")
        self._downgrade("-2")
        insp = self._inspect()
        self.assertNotIn("scan_failures", insp.get_table_names())
        self.assertIn("scan_jobs", insp.get_table_names())
        self.assertIn("crypto_assets", insp.get_table_names())

    def test_downgrade_to_base_removes_all(self):
        """Downgrading to base removes every table Alembic manages.

        The ``alembic_version`` tracking table is intentionally left behind
        by Alembic itself — it holds the current revision pointer.
        """
        self._upgrade("head")
        self._downgrade("base")
        insp = self._inspect()
        # alembic_version survives; every other table should be gone.
        tables = set(insp.get_table_names()) - {"alembic_version"}
        self.assertEqual(set(), tables,
                         "Expected no managed tables after downgrade to base")

    # ── data preservation ───────────────────────────────────────────────────

    def test_data_survives_upgrade(self):
        """Rows inserted after 0001 survive the 0002 upgrade."""
        self._upgrade("69254661dfed")
        with self._engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO scan_jobs (repo_path, status)
                VALUES ('/test', 'completed')
            """))
            conn.execute(text("""
                INSERT INTO crypto_assets (scan_job_id, algorithm, location, source)
                VALUES (1, 'RSA-2048', '/src/crypto.py', '[]')
            """))
        self._upgrade("a7f3c2e91d04")
        with self._engine.connect() as conn:
            job_count = conn.execute(text("SELECT COUNT(*) FROM scan_jobs")).scalar()
            asset_count = conn.execute(text("SELECT COUNT(*) FROM crypto_assets")).scalar()
        self.assertEqual(1, job_count)
        self.assertEqual(1, asset_count)

    def test_failure_insert_after_upgrade(self):
        """ScanFailureDB rows can be inserted after full upgrade."""
        self._upgrade("head")
        with self._engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO scan_jobs (repo_path, status)
                VALUES ('/test', 'completed')
            """))
            conn.execute(text("""
                INSERT INTO scan_failures (scan_job_id, path, reason)
                VALUES (1, 'foo.py', 'unreadable')
            """))
        with self._engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM scan_failures")).scalar()
        self.assertEqual(1, count)

    # ── migration graph ─────────────────────────────────────────────────────

    def test_linear_migration_graph(self):
        """Revisions form a single linear chain: 0001 -> 0002 -> 0003."""
        script = ScriptDirectory.from_config(_make_config(self.db_url))
        # walk_revisions() returns newest-to-oldest; reverse to oldest-first.
        revs = list(reversed(list(script.walk_revisions())))
        self.assertEqual(3, len(revs))
        prev = None
        for rev in revs:
            self.assertEqual(prev, rev.down_revision,
                             f"Broken chain at {rev.revision}")
            prev = rev.revision


if __name__ == "__main__":
    unittest.main()
