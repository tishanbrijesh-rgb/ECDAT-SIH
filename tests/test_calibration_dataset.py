"""Tests for CalibrationDataset — Phase 4 empirical calibration support."""
from __future__ import annotations

import os
import tempfile

from backend.services.calibration import (
    CalibrationParameters,
    classify_confidence,
)
from backend.services.calibration_dataset import (
    CalibrationDataset,
    CalibrationRecord,
)


def _make_record(confidence, outcome, algorithm="RSA", source="ast", band=None, context_hash=None):
    if band is None:
        band = classify_confidence(confidence)["band"]
    if context_hash is None:
        context_hash = f"{algorithm}-{source}-{id(confidence)}"
    return CalibrationRecord(
        confidence=confidence,
        outcome=outcome,
        algorithm=algorithm,
        source=source,
        evidence_kind="observed_operation",
        band=band,
        context_hash=context_hash,
    )


class TestCalibrationRecord:
    def test_defaults(self):
        r = _make_record(0.8, 1)
        assert r.confidence == 0.8
        assert r.outcome == 1
        assert r.algorithm == "RSA"
        assert r.context_hash


class TestCalibrationDataset:
    def test_empty_dataset(self):
        ds = CalibrationDataset()
        assert ds.count() == 0
        assert len(ds) == 0

    def test_add_records_dedup(self):
        ds = CalibrationDataset()
        r1 = _make_record(0.8, 1, context_hash="abc")
        r2 = _make_record(0.9, 1, context_hash="abc")
        r3 = _make_record(0.7, 0, context_hash="def")
        added = ds.add_records([r1, r2, r3])
        assert added == 2
        assert ds.count() == 2

    def test_save_and_load_roundtrip(self):
        ds = CalibrationDataset()
        ds.add_records([_make_record(0.9, 1), _make_record(0.5, 0)])
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            path = f.name
        try:
            saved = ds.save(path)
            assert os.path.exists(saved)
            ds2 = CalibrationDataset()
            ds2.load(saved)
            assert ds2.count() == 2
            assert ds2.records[0].confidence == 0.9
        finally:
            os.unlink(path)

    def test_compute_metrics_empty(self):
        ds = CalibrationDataset()
        m = ds.compute_metrics()
        assert m["sample_count"] == 0
        assert m["overall"]["brier_score"] is None

    def test_compute_metrics_populated(self):
        ds = CalibrationDataset()
        for i in range(30):
            ds.add_records([_make_record(0.9 + i * 0.001, 1, context_hash=f"h{i}-{j}") for j in range(3)])
        m = ds.compute_metrics()
        assert m["sample_count"] == 90
        assert m["overall"]["accuracy"] == 1.0
        assert m["overall"]["brier_score"] is not None
        assert m["per_band"]["HIGH"]["count"] == 90

    def test_per_band_breakdown(self):
        ds = CalibrationDataset()
        ds.add_records([
            _make_record(0.95, 1, band="HIGH", context_hash="h1"),
            _make_record(0.95, 1, band="HIGH", context_hash="h2"),
            _make_record(0.70, 1, band="MEDIUM", context_hash="h3"),
            _make_record(0.50, 0, band="LOW", context_hash="h4"),
        ])
        m = ds.compute_metrics()
        assert m["per_band"]["HIGH"]["count"] == 2
        assert m["per_band"]["MEDIUM"]["count"] == 1
        assert m["per_band"]["LOW"]["count"] == 1
        assert m["per_band"]["LOW"]["accuracy"] == 0.0

    def test_drift_report_no_drift(self):
        ds = CalibrationDataset()
        for i in range(30):
            ds.add_records([_make_record(0.82, 1, context_hash=f"nd{i}") for _ in range(5)])
        params = CalibrationParameters(brier_score=0.03, ece=0.02)
        report = ds.drift_report(params)
        assert report["overall_status"] == "OK"

    def test_drift_report_with_drift(self):
        ds = CalibrationDataset()
        for i in range(30):
            ds.add_records([_make_record(0.95, 0, context_hash=f"d{i}")])
        params = CalibrationParameters(brier_score=0.50, ece=0.50)
        report = ds.drift_report(params)
        high_check = next(c for c in report["checks"] if c["band"] == "HIGH")
        assert high_check["status"] == "DRIFT"
        assert report["overall_status"] == "DRIFT_DETECTED"

    def test_drift_skips_small_bands(self):
        ds = CalibrationDataset()
        ds.add_records([_make_record(0.95, 0, context_hash="s1")])
        params = CalibrationParameters(brier_score=0.50, ece=0.50)
        report = ds.drift_report(params)
        assert report["checks"] == []

    def test_add_from_scan(self):
        ds = CalibrationDataset()
        assets = [
            {
                "confidence": 0.9,
                "confirmed_use": True,
                "algorithm": "RSA",
                "source": ["ast"],
                "evidence_kind": "observed_operation",
                "location": "app/crypto.py",
                "evidence_json": {"operation_anchor": "line-10"},
            },
            {
                "confidence": 0.5,
                "confirmed_use": False,
                "algorithm": "AES",
                "source": ["rule"],
                "evidence_kind": "declared_capability",
                "location": "lib/crypto.go",
                "evidence_json": {"operation_anchor": "line-5"},
            },
        ]
        added = ds.add_from_scan(assets)
        assert added == 2
        assert ds.count() == 2
        assert ds.records[0].outcome == 1
        assert ds.records[1].outcome == 0

    def test_clear(self):
        ds = CalibrationDataset()
        ds.add_records([_make_record(0.8, 1)])
        assert ds.count() == 1
        ds.clear()
        assert ds.count() == 0
