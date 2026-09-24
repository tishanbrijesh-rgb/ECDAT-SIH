"""Tests for the scan router endpoints."""
from __future__ import annotations

import types
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.models.scan_job import ScanJobDB


@pytest.fixture(autouse=True)
def _mock_external_deps():
    """Patch filesystem-dependent and subprocess-spawning calls."""
    import backend.routers.scan as _rs
    import backend.services.repository_guard as _rg
    import backend.services.scan_control as _sc

    _orig_resolve = _rg.resolve_repository
    _rg.resolve_repository = lambda raw: raw  # skip the real fs check
    # Also patch the local reference imported by the scan router
    _rs.resolve_repository = lambda raw: raw

    # Provide a dummy Control for reserve() so reserve() returns without
    # checking the real global _active slot.
    def _dummy_reserve(*_a, **_kw):
        return types.SimpleNamespace(
            scan_id=None,
            timeout=300,
            cancel=types.SimpleNamespace(is_set=lambda: False, set=lambda: None),
        )

    _orig_reserve = _rs.reserve
    _rs.reserve = _dummy_reserve
    _sc.reserve = _dummy_reserve

    # Patch claim/release/request_cancel at the scan-router level (post_scan imports them
    # directly, so patching backend.services.scan_control has no effect).
    _orig_claim = _rs.claim
    _orig_release = _rs.release
    _orig_request_cancel = _rs.request_cancel
    _rs.claim = lambda *a, **kw: None
    _rs.release = lambda *a, **kw: None
    _rs.request_cancel = lambda scan_id: None

    yield

    _rg.resolve_repository = _orig_resolve
    _rs.resolve_repository = _orig_resolve
    _rs.reserve = _orig_reserve
    _sc.reserve = _orig_reserve
    _rs.claim = _orig_claim
    _rs.release = _orig_release
    _rs.request_cancel = _orig_request_cancel


class TestScanEndpoints:
    """Integration tests for POST /api/scan, GET /api/scans,
    GET /api/scans/{id}, POST /api/scans/{id}/cancel,
    and GET /api/scans/{id}/events."""

    # ── POST /api/scan ────────────────────────────────────────────────────────

    def test_create_scan_returns_scan_id(self, client: TestClient):
        """POST /api/scan creates a job and returns its id."""
        resp = client.post(
            "/api/scan",
            json={"repo_path": "/some/repo"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "scan_id" in body
        assert isinstance(body["scan_id"], int)
        assert body["status"] == "started"

    def test_create_scan_job_is_persisted(self, client: TestClient):
        """After POST /api/scan, the job appears in the database."""
        resp = client.post(
            "/api/scan",
            json={"repo_path": "/some/repo"},
        )
        assert resp.status_code == 200
        scan_id = resp.json()["scan_id"]

        list_resp = client.get("/api/scans")
        assert list_resp.status_code == 200
        ids = [j["id"] for j in list_resp.json()]
        assert scan_id in ids

    def test_create_scan_missing_repo_path(self, client: TestClient):
        """POST /api/scan returns 422 when body is missing or empty."""
        resp = client.post("/api/scan", json={})
        assert resp.status_code == 422

        resp = client.post("/api/scan", json={"repo_path": ""})
        assert resp.status_code == 422

    # ── GET /api/scans ────────────────────────────────────────────────────────

    def test_list_scans_returns_list(self, client: TestClient):
        """GET /api/scans returns a list (empty when no jobs exist)."""
        resp = client.get("/api/scans")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)

    def test_list_scans_supports_pagination(self, client: TestClient):
        """GET /api/scans respects limit and offset query params."""
        resp = client.get("/api/scans?limit=10&offset=0")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert len(resp.json()) <= 10

    # ── GET /api/scans/{id} ───────────────────────────────────────────────────

    def test_get_scan_not_found(self, client: TestClient):
        """GET /api/scans/{id} returns 404 for a non-existent job."""
        resp = client.get("/api/scans/999999")
        assert resp.status_code == 404

    def test_get_scan_returns_job(self, client: TestClient):
        """GET /api/scans/{id} returns the matching ScanJobResponse."""
        create_resp = client.post(
            "/api/scan",
            json={"repo_path": "/some/repo"},
        )
        scan_id = create_resp.json()["scan_id"]

        resp = client.get(f"/api/scans/{scan_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == scan_id
        assert "status" in body
        assert body["repo_path"] == "/some/repo"
        assert body["assets_found"] == 0

    # ── POST /api/scans/{id}/cancel ───────────────────────────────────────────

    def test_cancel_scan_queued(self, client: TestClient):
        """POST /api/scans/{id}/cancel cancels a queued/running scan."""
        create_resp = client.post(
            "/api/scan",
            json={"repo_path": "/some/repo"},
        )
        scan_id = create_resp.json()["scan_id"]

        # Set scan to 'running' so the cancel endpoint accepts it.
        from backend.db import SessionLocal

        with SessionLocal() as db:
            job = db.get(ScanJobDB, scan_id)
            job.status = "running"
            db.commit()

        # Patch at the router level (cancel_scan imports request_cancel directly
        # from backend.services.scan_control, so patching that module has no
        # effect on the router's local reference).
        from unittest.mock import patch

        import backend.routers.scan as _rs
        with patch.object(_rs, "request_cancel") as mock_cancel:
            cancel_resp = client.post(f"/api/scans/{scan_id}/cancel")
        assert cancel_resp.status_code == 202
        body = cancel_resp.json()
        assert body["scan_id"] == scan_id
        assert body["status"] == "cancellation_requested"
        mock_cancel.assert_called_once_with(scan_id)

    def test_cancel_scan_already_completed(self, client: TestClient):
        """POST /api/scans/{id}/cancel returns 409 for a finished scan."""
        create_resp = client.post(
            "/api/scan",
            json={"repo_path": "/some/repo"},
        )
        scan_id = create_resp.json()["scan_id"]

        from backend.db import SessionLocal

        with SessionLocal() as db:
            job = db.get(ScanJobDB, scan_id)
            job.status = "completed"
            db.commit()

        resp = client.post(f"/api/scans/{scan_id}/cancel")
        assert resp.status_code == 409

    def test_cancel_scan_not_found(self, client: TestClient):
        """POST /api/scans/{id}/cancel returns 404 for a non-existent job."""
        resp = client.post("/api/scans/999999/cancel")
        assert resp.status_code == 404

    # ── GET /api/scans/{id}/events ─────────────────────────────────────────────

    def test_sse_events_returns_streaming(self, client: TestClient):
        """GET /api/scans/{id}/events returns a streaming response that terminates."""
        with patch("backend.services.scan_control.claim"):
            with patch("backend.services.scan_control.release"):
                with patch("backend.security.record_audit"):
                    create_resp = client.post(
                        "/api/scan",
                        json={"repo_path": "/some/repo"},
                    )
        scan_id = create_resp.json()["scan_id"]

        # Use a small max_events bound so the stream terminates cleanly in tests.
        resp = client.get(f"/api/scans/{scan_id}/events?max_events=5")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "text/event-stream; charset=utf-8"
        # Verify the stream actually terminates (body is non-empty and bounded).
        body = resp.text
        assert len(body) > 0
        assert len(body) < 10000  # Should not grow without bound.

    def test_sse_events_not_found(self, client: TestClient):
        """GET /api/scans/{id}/events returns 404 for a non-existent job."""
        resp = client.get("/api/scans/999999/events")
        assert resp.status_code == 404
