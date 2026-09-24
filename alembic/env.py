"""Alembic migration environment for ECDAT."""
# ruff: noqa: F401, I001
from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from alembic import context

# Ensure backend package is importable
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
load_dotenv(REPO_ROOT / ".env", override=False)

from backend.db import DATABASE_URL, Base
from backend.models.scan_job import ScanJobDB
from backend.models.asset import CryptoAssetDB
from backend.models.audit_log import AuditLogDB

# ScanFailureDB may not exist during baseline migration generation;
# import it if available so autogenerate can detect new tables.
try:
    from backend.models.scan_failure import ScanFailureDB
except ImportError:  # pragma: no cover
    ScanFailureDB = None  # type: ignore[assignment,misc]

try:
    from backend.models.scan_lease import ScanLeaseDB
except ImportError:  # pragma: no cover
    ScanLeaseDB = None  # type: ignore[assignment,misc]

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    return os.getenv("DATABASE_URL", DATABASE_URL)


def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(get_url(), pool_pre_ping=True)
    try:
        with connectable.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,
                compare_server_default=True,
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
