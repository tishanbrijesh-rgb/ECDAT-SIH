"""Durable scan admission, lease, cancellation, and result regressions."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.db import Base


def _session_factory():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)


def test_enqueue_persists_job_and_dispatch_in_one_commit() -> None:
    from backend.models.scan_dispatch import ScanDispatchDB
    from backend.models.scan_job import ScanJobDB
    from backend.services.scan_control import enqueue_scan

    engine, factory = _session_factory()
    try:
        with factory() as db:
            scan_id = enqueue_scan(db, "/repo")
        with factory() as db:
            job = db.get(ScanJobDB, scan_id)
            dispatch = db.query(ScanDispatchDB).filter_by(scan_job_id=scan_id).one()
            assert job is not None
            assert job.status == "queued"
            assert dispatch.state == "pending"
            assert dispatch.version == 1
    finally:
        engine.dispose()


def test_enqueue_reuses_active_job_for_the_same_repository() -> None:
    """Repeated start requests must not create duplicate queued scans."""
    from backend.models.scan_dispatch import ScanDispatchDB
    from backend.models.scan_job import ScanJobDB
    from backend.services.scan_control import enqueue_scan

    engine, factory = _session_factory()
    try:
        with factory() as db:
            first_id = enqueue_scan(db, "/repo")
        with factory() as db:
            repeated_id = enqueue_scan(db, "/repo")

        assert repeated_id == first_id
        with factory() as db:
            assert db.query(ScanJobDB).count() == 1
            assert db.query(ScanDispatchDB).count() == 1
    finally:
        engine.dispose()


def test_post_scan_enqueues_before_process_local_dispatch() -> None:
    from backend.routers import scan

    engine, factory = _session_factory()
    background = MagicMock()
    try:
        with (
            patch.object(scan, "SessionLocal", factory),
            patch.object(scan, "resolve_repository", return_value="/repo"),
            patch.object(scan, "record_audit"),
            patch.object(scan, "reserve", side_effect=AssertionError("must not reserve in request")),
        ):
            result = scan.post_scan.__wrapped__(
                MagicMock(), scan.ScanRequest(repo_path="/repo"), background, "admin"
            )

        assert result["status"] == "started"
        assert background.add_task.call_args.args[1] == result["scan_id"]
    finally:
        engine.dispose()


def test_dispatch_claim_is_compare_and_set_across_sessions() -> None:
    from backend.services.scan_control import claim_dispatch, enqueue_scan

    engine, factory = _session_factory()
    try:
        with factory() as db:
            scan_id = enqueue_scan(db, "/repo")
        now = datetime.now(timezone.utc)
        with factory() as first:
            assert claim_dispatch(first, scan_id, "worker-a", now, timedelta(minutes=1))
            first.commit()
        with factory() as second:
            assert not claim_dispatch(second, scan_id, "worker-b", now, timedelta(minutes=1))
    finally:
        engine.dispose()


def test_cancel_request_reaches_remote_worker_through_database() -> None:
    from backend.models.scan_dispatch import ScanDispatchDB
    from backend.services import scan_control

    engine, factory = _session_factory()
    try:
        with factory() as db:
            scan_id = scan_control.enqueue_scan(db, "/repo")
        with (
            patch.object(scan_control, "SessionLocal", factory),
            patch.object(scan_control, "_active", None),
        ):
            scan_control.request_cancel(scan_id)

        with factory() as db:
            dispatch = db.query(ScanDispatchDB).filter_by(scan_job_id=scan_id).one()
            assert dispatch.state == "cancel_requested"
            assert dispatch.cancellation_requested_at is not None
    finally:
        engine.dispose()


def test_supervisor_observes_remote_cancellation() -> None:
    from backend.services import scan_control

    process = MagicMock(returncode=None)
    process.poll.return_value = None
    process.wait.return_value = 0
    control = MagicMock(scan_id=7, timeout=0)
    control.durable_claim = True
    control.cancel.is_set.return_value = False
    control.cancel.wait.return_value = False

    with (
        patch.object(scan_control.subprocess, "Popen", return_value=process),
        patch.object(scan_control, "cancellation_requested", return_value=True),
        patch.object(scan_control, "_terminate_process_tree"),
        patch.object(scan_control, "_finish_if_active") as finish,
        patch.object(scan_control, "finalize_dispatch"),
        patch.object(scan_control, "release"),
    ):
        scan_control.supervise("/repo", control)

    assert finish.call_args.args[1] == "cancelled"


def test_lease_heartbeat_requires_live_matching_owner() -> None:
    from backend.models.scan_job import ScanJobDB
    from backend.services.scan_lease import acquire_lease, heartbeat_lease

    engine, factory = _session_factory()
    now = datetime.now(timezone.utc)
    ttl = timedelta(seconds=30)
    try:
        with factory() as db:
            job = ScanJobDB(repo_path="/repo", status="running")
            db.add(job)
            db.commit()
            scan_id = job.id
            assert acquire_lease(db, scan_id, worker_id="worker-a", now=now, ttl=ttl)
            db.commit()

        with factory() as db:
            assert not heartbeat_lease(
                db, scan_id, "worker-b", now + timedelta(seconds=5), ttl
            )
            assert heartbeat_lease(
                db, scan_id, "worker-a", now + timedelta(seconds=5), ttl
            )
            db.commit()

        with factory() as db:
            assert not heartbeat_lease(
                db, scan_id, "worker-a", now + timedelta(minutes=2), ttl
            )
    finally:
        engine.dispose()


def test_dispatch_heartbeat_requires_live_matching_owner() -> None:
    from backend.models.scan_dispatch import ScanDispatchDB
    from backend.services.scan_control import (
        claim_dispatch,
        enqueue_scan,
        heartbeat_dispatch,
    )

    engine, factory = _session_factory()
    ttl = timedelta(seconds=30)
    try:
        with factory() as db:
            scan_id = enqueue_scan(db, "/repo")
        claimed_at = datetime.now(timezone.utc)
        with factory() as db:
            assert claim_dispatch(db, scan_id, "worker-a", claimed_at, ttl)
            db.commit()

        heartbeat_at = claimed_at + timedelta(seconds=5)
        with factory() as db:
            assert not heartbeat_dispatch(db, scan_id, "worker-b", heartbeat_at, ttl)
            assert heartbeat_dispatch(db, scan_id, "worker-a", heartbeat_at, ttl)
            db.commit()

        with factory() as db:
            dispatch = db.query(ScanDispatchDB).filter_by(scan_job_id=scan_id).one()
            assert dispatch.heartbeat_at is not None
    finally:
        engine.dispose()


def test_duplicate_result_delivery_does_not_duplicate_assets() -> None:
    from backend.models.asset import CryptoAssetDB
    from backend.models.scan_job import ScanJobDB
    from backend.services.scanner_runner import persist_scan_result

    engine, factory = _session_factory()
    result = {
        "findings": [
            {
                "algorithm": "RSA",
                "category": "asymmetric",
                "sources": ["ast"],
                "location": "src/example.py:1",
                "evidence_kind": "observed_operation",
                "usage": "encryption",
                "logical_asset_id": "rsa-example",
                "evidence_list": [],
            }
        ],
        "metrics": {"total_files": 1, "in_scope_files": 1, "scanned_files": 1},
    }
    try:
        with factory() as db:
            job = ScanJobDB(repo_path="/repo", status="running")
            db.add(job)
            db.commit()
            scan_id = job.id

        first = persist_scan_result(scan_id, result, result_version=1, session_factory=factory)
        duplicate = persist_scan_result(scan_id, result, result_version=1, session_factory=factory)

        assert first == duplicate
        with factory() as db:
            assert db.query(CryptoAssetDB).filter_by(scan_job_id=scan_id).count() == 1
    finally:
        engine.dispose()


def test_dispatch_scan_claims_outbox_before_supervision() -> None:
    from backend.models.scan_dispatch import ScanDispatchDB
    from backend.models.scan_job import ScanJobDB
    from backend.services import scan_control

    engine, factory = _session_factory()
    control = SimpleNamespace(
        scan_id=1,
        worker_id="worker-a",
        timeout=300,
        version=1,
    )
    try:
        with factory() as db:
            scan_id = scan_control.enqueue_scan(db, "/repo")
        control.scan_id = scan_id
        with (
            patch.object(scan_control, "SessionLocal", factory),
            patch.object(scan_control, "reserve", return_value=control),
            patch.object(scan_control, "supervise") as supervise,
        ):
            assert scan_control.dispatch_scan(scan_id)

        supervise.assert_called_once_with("/repo", control)
        with factory() as db:
            dispatch = db.query(ScanDispatchDB).filter_by(scan_job_id=scan_id).one()
            job = db.get(ScanJobDB, scan_id)
            assert dispatch.state == "claimed"
            assert dispatch.claimed_by == "worker-a"
            assert job is not None and job.status == "running"
    finally:
        engine.dispose()
