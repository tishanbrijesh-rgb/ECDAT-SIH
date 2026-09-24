"""Verify that all Alembic migrations apply cleanly from an empty database."""
from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
from pathlib import Path

from alembic.config import Config

from alembic import command

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"
SCRIPT_LOCATION = Path(__file__).resolve().parents[2] / "alembic"


def _alembic_config(db_url: str) -> Config:
    """Build an Alembic config pointing at a specific database URL."""
    cfg = Config(str(ALEMBIC_INI))
    cfg.config_file_name = None
    cfg.set_main_option("script_location", str(SCRIPT_LOCATION))
    # env.py get_url() reads DATABASE_URL env var; set it so the migration
    # engine connects to our temp file rather than the default ecdat.db.
    os.environ["DATABASE_URL"] = db_url
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def test_migrations_apply_from_empty() -> None:
    """All migrations apply cleanly from an empty SQLite database."""
    tmpdir = tempfile.mkdtemp()
    try:
        db_path = Path(tmpdir) / "test_migrate.db"
        db_url = "sqlite:///" + str(db_path)
        cfg = _alembic_config(db_url)

        command.upgrade(cfg, "head")

        conn = sqlite3.connect(str(db_path))
        try:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            for required in (
                "scan_jobs",
                "crypto_assets",
                "scan_failures",
                "audit_logs",
                "scan_leases",
            ):
                assert required in tables, f"Missing table: {required}"
            revision = conn.execute(
                "SELECT version_num FROM alembic_version"
            ).fetchone()[0]
            assert revision is not None and len(revision) > 0
        finally:
            conn.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_migrations_idempotent() -> None:
    """Running upgrade twice does not fail."""
    tmpdir = tempfile.mkdtemp()
    try:
        db_path = Path(tmpdir) / "test_idempotent.db"
        db_url = "sqlite:///" + str(db_path)
        cfg = _alembic_config(db_url)

        command.upgrade(cfg, "head")
        command.upgrade(cfg, "head")

        conn = sqlite3.connect(str(db_path))
        try:
            revision = conn.execute(
                "SELECT version_num FROM alembic_version"
            ).fetchone()[0]
            assert revision is not None
        finally:
            conn.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_migration_0005_adds_evidence_columns() -> None:
    """Migration 0005 columns are present after full upgrade."""
    tmpdir = tempfile.mkdtemp()
    try:
        db_path = Path(tmpdir) / "test_0005.db"
        db_url = "sqlite:///" + str(db_path)
        cfg = _alembic_config(db_url)

        command.upgrade(cfg, "head")

        conn = sqlite3.connect(str(db_path))
        try:
            cols = {
                row[1]
                for row in conn.execute("PRAGMA table_info(crypto_assets)").fetchall()
            }
            for col in (
                "evidence_kind",
                "parser_version",
                "evidence_quality",
                "confirmed_use",
                "capability_only",
                "span",
                "confidence_reasons",
            ):
                assert col in cols, f"Missing column after migration 0005: {col}"
        finally:
            conn.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_migration_downgrade_to_0004() -> None:
    """Downgrade from the current head to 0004 removes later columns cleanly."""
    tmpdir = tempfile.mkdtemp()
    try:
        db_path = Path(tmpdir) / "test_downgrade.db"
        db_url = "sqlite:///" + str(db_path)
        cfg = _alembic_config(db_url)

        command.upgrade(cfg, "head")
        command.downgrade(cfg, "f9c6d3a18b72")

        conn = sqlite3.connect(str(db_path))
        try:
            revision = conn.execute(
                "SELECT version_num FROM alembic_version"
            ).fetchone()[0]
            assert revision == "f9c6d3a18b72", f"Expected 0004, got {revision}"
            cols = {
                row[1]
                for row in conn.execute("PRAGMA table_info(crypto_assets)").fetchall()
            }
            # 0005 columns must be removed
            for col in (
                "evidence_kind",
                "parser_version",
                "evidence_quality",
                "confirmed_use",
                "capability_only",
                "span",
                "confidence_reasons",
            ):
                assert col not in cols, (
                    f"Column {col} should be removed after downgrade to 0004"
                )
            # 0006 column must also be removed
            assert "risk_context_provenance" not in cols, (
                "Column risk_context_provenance should be removed after downgrade"
            )
            # Original columns should still be present
            for col in ("algorithm", "priority_score", "priority_label"):
                assert col in cols, f"Column {col} missing after downgrade"
        finally:
            conn.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
