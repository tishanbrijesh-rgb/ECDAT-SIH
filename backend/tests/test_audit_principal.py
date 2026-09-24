"""Focused identity and transactional-audit regression tests."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.routers.assets as assets_router
import backend.routers.audit as audit_router
from backend import security
from backend.db import Base
from backend.models.asset import CryptoAssetDB
from backend.models.audit_log import AuditLogDB
from backend.models.scan_job import ScanJobDB
from backend.schemas.asset import AssetUpdate
from backend.security import Principal, current_role, issue_demo_token, role_from_token
from tests.integration_env import PASSWORD


def test_audit_principal_migration_follows_provenance_in_the_linear_chain() -> None:
    config = Config("alembic.ini")
    config.set_main_option("script_location", "alembic")

    revision = ScriptDirectory.from_config(config).get_revision("0007_audit_principal")
    assert revision is not None
    assert revision.down_revision == "0006_provenance"


def test_signed_session_resolves_to_a_complete_principal(monkeypatch) -> None:
    monkeypatch.setattr(security, "_is_session_revoked", lambda _session_id: False)
    token = issue_demo_token("analyst", PASSWORD)["access_token"]

    principal = role_from_token(str(token))

    assert principal == "security_analyst"
    assert principal.subject == "analyst"
    assert principal.role == "security_analyst"
    assert principal.expires_at > 0
    assert principal.session_id


def test_revoked_session_is_rejected_on_next_token_verification(monkeypatch) -> None:
    from backend.security import revoke_session

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(security, "SessionLocal", factory)
    token = str(issue_demo_token("analyst", PASSWORD)["access_token"])
    principal = role_from_token(token)

    revoke_session(principal)

    with pytest.raises(HTTPException) as error:
        role_from_token(token)
    assert error.value.status_code == 401
    engine.dispose()


def test_demo_header_resolves_to_an_explicit_demo_principal() -> None:
    principal = current_role(authorization=None, x_ecdat_role="admin")

    assert principal == "admin"
    assert principal.subject == "demo-header:admin"
    assert principal.role == "admin"
    assert principal.expires_at == 0
    assert principal.session_id == "demo-header"


def test_audit_event_persists_complete_actor_identity(monkeypatch) -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(security, "SessionLocal", factory)
    principal = Principal("admin-a", "admin", 123456, "session-a")

    security.record_audit("asset.updated", "asset:1", principal, {"field": "exposure"})

    with factory() as db:
        event = db.query(AuditLogDB).one()
        assert event.actor_subject == "admin-a"
        assert event.actor_role == "admin"
        assert event.actor_session_id == "session-a"
        assert event.actor_expires_at == 123456
    engine.dispose()


def test_audit_history_exposes_actor_identity_fields(monkeypatch) -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        db.add(
            AuditLogDB(
                actor_subject="admin-c",
                actor_role="admin",
                actor_session_id="session-c",
                actor_expires_at=777,
                action="asset.updated",
                resource="asset:3",
            )
        )
        db.commit()
    monkeypatch.setattr(audit_router, "SessionLocal", factory)

    response = audit_router.audit_logs(
        limit=50,
        offset=0,
        role=Principal("auditor-a", "auditor", 888, "session-auditor"),
    )

    item = json.loads(response.body)[0]
    assert item["actor_subject"] == "admin-c"
    assert item["actor_role"] == "admin"
    assert item["actor_session_id"] == "session-c"
    assert item["actor_expires_at"] == 777
    engine.dispose()


def test_retention_purge_leaves_a_durable_actor_attributed_event(monkeypatch) -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        db.add(
            AuditLogDB(
                timestamp=datetime.now(timezone.utc) - timedelta(days=120),
                actor_subject="old-admin",
                actor_role="admin",
                actor_session_id="old-session",
                action="old.event",
                resource="asset:1",
            )
        )
        db.commit()

    monkeypatch.setattr(audit_router, "SessionLocal", factory)
    principal = Principal("admin-b", "admin", 654321, "session-b")

    result = audit_router.purge_old_audit_logs(days=90, role=principal)

    assert result["deleted"] == 1
    with factory() as db:
        events = db.query(AuditLogDB).all()
        assert len(events) == 1
        purge = events[0]
        assert purge.action == "audit.retention_purged"
        assert purge.actor_subject == "admin-b"
        assert purge.actor_role == "admin"
        assert purge.details["days"] == 90
        assert purge.details["deleted"] == 1
        assert purge.details["cutoff"] == result["older_than"]
    engine.dispose()


def test_asset_mutation_rolls_back_when_audit_write_fails(monkeypatch) -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        scan = ScanJobDB(repo_path="fixture", status="completed")
        db.add(scan)
        db.flush()
        asset = CryptoAssetDB(
            scan_job_id=scan.id,
            algorithm="RSA",
            category="asymmetric",
            location="crypto.py:1",
            exposure="internal",
        )
        db.add(asset)
        db.commit()
        asset_id = asset.id

    monkeypatch.setattr(assets_router, "SessionLocal", factory)

    def fail_audit(*_args, **_kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(assets_router, "record_audit", fail_audit)
    principal = Principal("admin-a", "admin", 123456, "session-a")

    with pytest.raises(RuntimeError, match="audit unavailable"):
        assets_router.update_asset(asset_id, AssetUpdate(exposure="internet"), principal)

    with factory() as db:
        persisted = db.get(CryptoAssetDB, asset_id)
        assert persisted is not None
        assert persisted.exposure == "internal"
    engine.dispose()
