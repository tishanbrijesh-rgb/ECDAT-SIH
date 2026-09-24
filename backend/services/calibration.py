"""Confidence calibration for ECDAT discovery-assurance scoring.

Bands a 0-1 confidence score into interpretable buckets, provides
offline metrics (Brier score, ECE), and stores versioned calibration
parameters for reproducible experiments.

Phase 5: confidence calibration module.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# CalibrationBands class
# ---------------------------------------------------------------------------

class CalibrationBands:
    """Calibrated confidence bands derived from labeled data.

    Band thresholds are configurable but default to the Phase 5 specification:
        HIGH      >= 0.85  — verified by multiple sources
        MEDIUM    0.60-0.85 — single source, typical operation
        LOW       0.40-0.60 — weak signal or declared capability
        UNCERTAIN <  0.40  — indirect or inferred evidence
    """

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNCERTAIN = "UNCERTAIN"

    LABELS = {
        HIGH: "High confidence",
        MEDIUM: "Medium confidence",
        LOW: "Low confidence",
        UNCERTAIN: "Uncertain",
    }

    DESCRIPTIONS = {
        HIGH: "Verified by multiple sources — evidence is strong and consistent",
        MEDIUM: "Single source, typical operation — evidence is reliable but from one vantage point",
        LOW: "Weak signal or declared capability — evidence is suggestive but not confirmed",
        UNCERTAIN: "Indirect or inferred evidence — confidence is below actionable threshold",
    }

    DEFAULT_THRESHOLDS = {
        "HIGH": (0.85, 1.00),
        "MEDIUM": (0.60, 0.85),
        "LOW": (0.40, 0.60),
        "UNCERTAIN": (0.00, 0.40),
    }

    @classmethod
    def band_for(cls, score: float, thresholds: dict[str, tuple[float, float]] | None = None) -> str:
        """Return the band name for a given confidence score."""
        t = thresholds if thresholds is not None else cls.DEFAULT_THRESHOLDS
        score = max(0.0, min(1.0, float(score)))
        for band, (lo, hi) in t.items():
            if lo <= score <= hi:
                return band
        return cls.UNCERTAIN

    @classmethod
    def ordered(cls) -> list[str]:
        """Return bands in descending order of confidence."""
        return [cls.HIGH, cls.MEDIUM, cls.LOW, cls.UNCERTAIN]


# ---------------------------------------------------------------------------
# Band definitions (module-level constants for backward compatibility)
# ---------------------------------------------------------------------------

BAND_THRESHOLDS: dict[str, tuple[float, float]] = dict(CalibrationBands.DEFAULT_THRESHOLDS)

BAND_META: dict[str, dict[str, str]] = {
    CalibrationBands.HIGH: {
        "label":       "High Confidence",
        "description": "Finding is well-supported by multiple high-strength evidence sources",
    },
    CalibrationBands.MEDIUM: {
        "label":       "Medium Confidence",
        "description": "Finding has reasonable evidence but may need human verification",
    },
    CalibrationBands.LOW: {
        "label":       "Low Confidence",
        "description": "Finding relies on weak or sparse evidence; treat with caution",
    },
    CalibrationBands.UNCERTAIN: {
        "label":       "Uncertain",
        "description": "Finding has insufficient evidence to support action",
    },
}

CALIBRATION_PARAMS_PATH = os.path.join(
    os.path.dirname(__file__),
    "calibration_params.json",
)


# ---------------------------------------------------------------------------
# Band classification
# ---------------------------------------------------------------------------

def classify_confidence(score: float, thresholds: dict[str, tuple[float, float]] | dict[str, float] | None = None) -> dict[str, Any]:
    """Return a classification dict for *score* (0-1).

    Accepts either the default BAND_THRESHOLDS (tuple-range format) or a
    simple dict of {band_name: cutoff_float} for the lower bound of each band.
    """
    score = max(0.0, min(1.0, float(score)))
    if thresholds is None:
        thresholds = dict(BAND_THRESHOLDS)

    # Detect format: if values are tuples, use range matching; if floats, use cutoff matching.
    first_val = next(iter(thresholds.values())) if thresholds else 0.85
    band = "UNCERTAIN"

    if isinstance(first_val, (tuple, list)):
        # Range format: (low, high) inclusive
        for b, (lo, hi) in thresholds.items():
            if lo <= score <= hi:
                band = b
                break
    else:
        # Cutoff format: descending order, first threshold the score meets is the band
        for b, cutoff in sorted(thresholds.items(), key=lambda x: x[1], reverse=True):
            if score >= cutoff:
                band = b
                break

    meta = BAND_META.get(band, BAND_META["UNCERTAIN"])
    return {
        "band":       band,
        "label":      meta["label"],
        "description": meta["description"],
        "raw_score":  score,
    }


# ---------------------------------------------------------------------------
# Calibration metrics
# ---------------------------------------------------------------------------

def compute_brier_score(predictions: list[float], outcomes: list[float]) -> float:
    """Mean squared error between probabilistic predictions and binary outcomes."""
    if not predictions or len(predictions) != len(outcomes):
        raise ValueError("predictions and outcomes must be non-empty and equal length")
    n = len(predictions)
    return sum((p - o) ** 2 for p, o in zip(predictions, outcomes, strict=True)) / n


def compute_ece(
    predictions: list[float],
    outcomes: list[float],
    n_bins: int = 10,
) -> float:
    """Expected Calibration Error with uniform-width bins."""
    if not predictions or len(predictions) != len(outcomes):
        raise ValueError("predictions and outcomes must be non-empty and equal length")

    bin_acc, bin_conf, bin_counts = [], [], []
    for i in range(n_bins):
        lo = i / n_bins
        hi = (i + 1) / n_bins
        if i == n_bins - 1:
            mask = [(lo <= p <= hi) for p in predictions]
        else:
            mask = [(lo <= p < hi) for p in predictions]

        count = sum(mask)
        if count == 0:
            bin_acc.append(0.0)
            bin_conf.append(0.0)
            bin_counts.append(0)
        else:
            actuals = [o for o, m in zip(outcomes, mask, strict=True) if m]
            preds = [p for p, m in zip(predictions, mask, strict=True) if m]
            bin_acc.append(sum(actuals) / count)
            bin_conf.append(sum(preds) / count)
            bin_counts.append(count)

    total = len(predictions)
    ece = sum(
        (c / total) * abs(a - conf)
        for a, conf, c in zip(bin_acc, bin_conf, bin_counts, strict=True)
    )
    return ece


def reliability_data(
    predictions: list[float],
    outcomes: list[float],
    n_bins: int = 10,
) -> dict[str, Any]:
    """Return bin edges, mean confidence per bin, mean accuracy per bin, sample count.

    Used for plotting reliability diagrams.
    """
    if not predictions or len(predictions) != len(outcomes):
        return {
            "bin_edges": [i / n_bins for i in range(n_bins + 1)],
            "mean_confidence": [None] * n_bins,
            "mean_accuracy": [None] * n_bins,
            "sample_count": [0] * n_bins,
        }

    bin_edges = [i / n_bins for i in range(n_bins + 1)]
    bin_preds: list[list[float]] = [[] for _ in range(n_bins)]
    bin_outcomes: list[list[float]] = [[] for _ in range(n_bins)]

    for p, o in zip(predictions, outcomes, strict=True):
        idx = min(int(p * n_bins), n_bins - 1)
        bin_preds[idx].append(p)
        bin_outcomes[idx].append(o)

    mean_confidence: list[float | None] = []
    mean_accuracy: list[float | None] = []
    sample_count: list[int] = []

    for i in range(n_bins):
        count = len(bin_preds[i])
        sample_count.append(count)
        if count == 0:
            mean_confidence.append(None)
            mean_accuracy.append(None)
        else:
            mean_confidence.append(round(sum(bin_preds[i]) / count, 4))
            mean_accuracy.append(round(sum(bin_outcomes[i]) / count, 4))

    return {
        "bin_edges": bin_edges,
        "mean_confidence": mean_confidence,
        "mean_accuracy": mean_accuracy,
        "sample_count": sample_count,
    }


# ---------------------------------------------------------------------------
# Versioned calibration parameters
# ---------------------------------------------------------------------------

@dataclass
class CalibrationParameters:
    """Versioned calibration parameters for a confidence model."""
    version: str = "1.0.0"
    band_thresholds: dict[str, tuple[float, float]] = field(default_factory=lambda: dict(BAND_THRESHOLDS))
    brier_score: float | None = None
    ece: float | None = None
    last_calibrated: str = ""
    sample_count: int = 0


# Default instance for uncalibrated (first-run) state.
DEFAULT_PARAMS = CalibrationParameters(
    version="cal-v1",
    band_thresholds=dict(BAND_THRESHOLDS),
    brier_score=None,
    ece=None,
    last_calibrated="",
    sample_count=0,
)


def versioned_confidence(raw_score: float, params: CalibrationParameters) -> dict[str, Any]:
    """Return a versioned confidence dict recording which calibration set was used."""
    thresholds = params.band_thresholds
    band = "UNCERTAIN"
    for b, (lo, hi) in thresholds.items():
        if lo <= raw_score <= hi:
            band = b
            break
    meta = BAND_META[band]
    return {
        "raw_score": raw_score,
        "band":      band,
        "label":     meta["label"],
        "calibration_version": params.version,
    }


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

def export_calibration_params(params: CalibrationParameters, path: str | None = None) -> str:
    """Write calibration params to *path* and return the path."""
    path = path or CALIBRATION_PARAMS_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        json.dump(asdict(params), fh, indent=2)
    return path


def load_calibration_params(path: str | None = None) -> CalibrationParameters:
    """Read calibration params from disk; return defaults on first run."""
    path = path or CALIBRATION_PARAMS_PATH
    if not os.path.exists(path):
        return CalibrationParameters()
    with open(path) as fh:
        data = json.load(fh)
    raw_thresholds = data.get("band_thresholds")
    if isinstance(raw_thresholds, dict):
        data["band_thresholds"] = {
            band: tuple(bounds) if isinstance(bounds, list) else bounds
            for band, bounds in raw_thresholds.items()
        }
    return CalibrationParameters(**data)
