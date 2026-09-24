"""Regression tests for persisted confidence calibration parameters."""

import json
import os
import shutil
import tempfile

from backend.services.calibration import classify_confidence, load_calibration_params


def test_json_range_thresholds_are_classified():
    """Classification uses the persisted band thresholds correctly."""
    tmpdir = tempfile.mkdtemp(prefix="ecdat-calibration-")
    try:
        path = os.path.join(tmpdir, "calibration_params.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "version": "test-v1",
                "band_thresholds": {
                    "HIGH": [0.85, 1.0],
                    "MEDIUM": [0.60, 0.85],
                    "LOW": [0.40, 0.60],
                    "UNCERTAIN": [0.0, 0.40],
                },
                "brier_score": 0.1,
                "ece": 0.05,
                "last_calibrated": "2026-01-01T00:00:00Z",
                "sample_count": 10,
            }, f)

        params = load_calibration_params(path)

        assert classify_confidence(0.8, params.band_thresholds)["band"] == "MEDIUM"
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
