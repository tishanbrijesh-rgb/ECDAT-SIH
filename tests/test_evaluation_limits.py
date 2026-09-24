"""Resource-boundary tests for ground-truth evaluation inputs."""

from __future__ import annotations

import json

from backend.services.evaluation import _load_ground_truth


def test_ground_truth_rejects_excessive_asset_count(tmp_path):
    payload = {
        "assets": [
            {"component": "c", "algorithm": "RSA"}
            for _ in range(10_001)
        ]
    }
    (tmp_path / "ground_truth.json").write_text(json.dumps(payload), encoding="utf-8")

    truth, error = _load_ground_truth(str(tmp_path))

    assert truth is None
    assert error is not None
    assert "10,000 assets" in error["message"]
