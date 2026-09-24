"""Read-only calibration and operational metrics endpoints."""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from backend.security import current_role

router = APIRouter()


@router.get("/api/calibration")
def calibration_status() -> dict:
    from backend.services.calibration import CalibrationBands, load_calibration_params

    params = load_calibration_params()
    definitions = {
        band: {
            "label": CalibrationBands.LABELS[band],
            "description": CalibrationBands.DESCRIPTIONS[band],
        }
        for band in CalibrationBands.ordered()
    }
    return {
        "version": params.version,
        "band_definitions": definitions,
        "band_thresholds": dict(params.band_thresholds),
        "metrics": {
            "brier_score": params.brier_score,
            "ece": params.ece,
            "sample_count": params.sample_count,
        },
        "last_calibrated": params.last_calibrated,
    }


@router.get("/api/admin/metrics")
def admin_metrics(role: str = Depends(current_role)) -> dict:
    if role != "admin":
        raise HTTPException(403, "Admin role required")
    from backend.services.scan_metrics import scan_metrics

    return scan_metrics.percentile_ranks()


if os.getenv("ECDAT_ENABLE_PROMETHEUS", "false").lower() == "true":

    @router.get("/metrics")
    def prometheus_metrics(role: str = Depends(current_role)) -> Response:
        if role != "admin":
            raise HTTPException(403, "Admin role required")
        from backend.services.prometheus_metrics import render_prometheus

        return Response(render_prometheus(), media_type="text/plain; version=0.0.4")
