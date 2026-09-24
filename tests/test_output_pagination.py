"""Stable pagination contracts for interactive output endpoints."""

from backend.models.asset import CryptoAssetDB
from backend.models.scan_job import ScanJobDB
from backend.routers import outputs
from tests.test_api_contract import _auth_headers


def _seed_ranked_assets() -> int:
    from backend.db import SessionLocal

    with SessionLocal() as db:
        scan = ScanJobDB(
            repo_path="/pagination-contract",
            status="completed",
            assets_found=4,
            coverage_pct=100.0,
        )
        db.add(scan)
        db.flush()
        for algorithm, score, label in (
            ("Zulu", 50, "HIGH"),
            ("Alpha", 90, "CRITICAL"),
            ("Bravo", 90, "CRITICAL"),
            ("Charlie", 10, "LOW"),
        ):
            db.add(
                CryptoAssetDB(
                    scan_job_id=scan.id,
                    logical_asset_id=f"asset-{algorithm.lower()}",
                    algorithm=algorithm,
                    location=f"src/{algorithm.lower()}.py",
                    source=["rule"],
                    priority_score=score,
                    priority_label=label,
                )
            )
        db.commit()
        return int(scan.id)


def test_risk_report_has_stable_filtered_page_boundaries(isolated_client):
    scan_id = _seed_ranked_assets()
    response = isolated_client.get(
        f"/api/reports/risk?scan_id={scan_id}&risk=CRITICAL&limit=1&offset=1",
        headers=_auth_headers(isolated_client),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["pagination"] == {
        "total": 4,
        "filtered": 2,
        "offset": 1,
        "limit": 1,
        "loaded": 1,
    }
    assert [item["algorithm"] for item in payload["migration_priorities"]] == ["Bravo"]


def test_cbom_filters_before_applying_a_stable_page_boundary(isolated_client):
    scan_id = _seed_ranked_assets()
    response = isolated_client.get(
        f"/api/cbom?scan_id={scan_id}&q=charlie&limit=1&offset=0",
        headers=_auth_headers(isolated_client),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["pagination"] == {
        "total": 4,
        "filtered": 1,
        "offset": 0,
        "limit": 1,
        "loaded": 1,
    }
    assert [item["name"] for item in payload["components"]] == ["Charlie"]


def test_cbom_csv_export_is_complete_and_separate_from_interactive_page(isolated_client):
    scan_id = _seed_ranked_assets()
    headers = _auth_headers(isolated_client)

    page = isolated_client.get(
        f"/api/cbom?scan_id={scan_id}&limit=1", headers=headers
    ).json()
    exported = isolated_client.get(f"/api/cbom.csv?scan_id={scan_id}", headers=headers)

    assert page["pagination"]["loaded"] == 1
    assert exported.status_code == 200
    assert exported.headers["x-exported-count"] == "4"
    assert len(exported.text.strip().splitlines()) == 5


def test_risk_csv_export_is_complete_and_separate_from_active_filter(isolated_client):
    scan_id = _seed_ranked_assets()
    headers = _auth_headers(isolated_client)

    page = isolated_client.get(
        f"/api/reports/risk?scan_id={scan_id}&risk=CRITICAL&limit=1", headers=headers
    ).json()
    exported = isolated_client.get(
        f"/api/reports/risk.csv?scan_id={scan_id}", headers=headers
    )

    assert page["pagination"]["filtered"] == 2
    assert page["pagination"]["loaded"] == 1
    assert exported.status_code == 200
    assert exported.headers["x-exported-count"] == "4"
    assert len(exported.text.strip().splitlines()) == 5


def test_evidence_graph_enforces_explicit_node_and_edge_limits(
    isolated_client, monkeypatch
):
    scan_id = _seed_ranked_assets()
    monkeypatch.setattr(outputs, "GRAPH_ASSET_LIMIT", 4)
    monkeypatch.setattr(outputs, "GRAPH_NODE_LIMIT", 3)
    monkeypatch.setattr(outputs, "GRAPH_EDGE_LIMIT", 1)

    response = isolated_client.get(
        f"/api/evidence-graph?scan_id={scan_id}",
        headers=_auth_headers(isolated_client),
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["nodes"]) == 3
    assert len(payload["edges"]) == 1
    assert payload["truncation"] == {
        "truncated": True,
        "limits": {"assets": 4, "nodes": 3, "edges": 1},
        "returned": {"assets": 2, "nodes": 3, "edges": 1},
        "total_assets": 4,
        "reasons": ["node_limit", "edge_limit"],
    }


def test_evaluation_rejects_scans_beyond_explicit_row_budget(
    isolated_client, monkeypatch
):
    scan_id = _seed_ranked_assets()
    monkeypatch.setattr(outputs, "EVALUATION_ASSET_LIMIT", 3)

    response = isolated_client.get(
        f"/api/evaluation?scan_id={scan_id}",
        headers=_auth_headers(isolated_client),
    )

    assert response.status_code == 413
    assert "3 assets" in response.json()["detail"]
