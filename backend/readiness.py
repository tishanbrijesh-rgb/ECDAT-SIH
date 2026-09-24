"""Database and configuration readiness checks for the API process."""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from collections.abc import Set as AbstractSet

from fastapi import HTTPException
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from backend.settings import SettingsError, get_settings


def missing_columns(insp, requirements: Mapping[str, AbstractSet[str]]) -> set[str]:
    missing: set[str] = set()
    tables = set(insp.get_table_names())
    for table, required in requirements.items():
        if table in tables:
            missing |= set(required) - {column["name"] for column in insp.get_columns(table)}
    return missing


def check_readiness(
    *,
    schema_revision: str,
    required_tables: set[str],
    required_columns: Mapping[str, AbstractSet[str]],
    logger: logging.Logger,
) -> dict[str, str | None]:
    """Validate configuration, connectivity, migration revision, and columns."""
    from backend.db import SessionLocal

    try:
        get_settings()
    except SettingsError as exc:
        logger.error("Readiness configuration validation failed: %s", exc)
        raise HTTPException(503, "Service configuration is invalid") from None

    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        inspector = inspect(db.get_bind())
        if not required_tables.issubset(set(inspector.get_table_names())):
            raise HTTPException(503, "Database schema is missing or incomplete")
        auto_create = os.getenv("ECDAT_AUTO_CREATE_TABLES", "false").lower() == "true"
        revision = db.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
        _validate_revision(revision, schema_revision, auto_create)
        if auto_create:
            missing = missing_columns(inspector, required_columns)
            if missing:
                names = ", ".join(sorted(missing))
                raise HTTPException(503, f"Database schema is missing columns: {names} — run 'alembic upgrade head'")
        return {"status": "ready", "database": "reachable", "revision": revision}
    except HTTPException:
        raise
    except SQLAlchemyError:
        raise HTTPException(503, "Database is unavailable or schema validation failed") from None
    finally:
        db.close()


def _validate_revision(revision: str | None, expected: str, auto_create: bool) -> None:
    if revision is None and not auto_create:
        raise HTTPException(503, "Database schema is not versioned — run 'alembic upgrade head' or set ECDAT_AUTO_CREATE_TABLES=true for development")
    if revision is not None and revision != expected:
        raise HTTPException(503, f"Database schema migration is stale: expected {expected}, found {revision} — run 'alembic upgrade head'")
