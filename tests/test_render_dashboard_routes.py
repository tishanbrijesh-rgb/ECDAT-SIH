"""Render's static mount must serve the SPA for client-side routes."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.render_app import DashboardFiles


def test_client_route_returns_dashboard_and_missing_asset_stays_404(tmp_path) -> None:
    (tmp_path / "index.html").write_text("<main>ECDAT dashboard</main>", encoding="utf-8")
    app = FastAPI()
    app.mount("/", DashboardFiles(directory=str(tmp_path), html=True))

    with TestClient(app) as client:
        route = client.get("/scan")
        asset = client.get("/missing.js")

    assert route.status_code == 200
    assert "ECDAT dashboard" in route.text
    assert asset.status_code == 404
