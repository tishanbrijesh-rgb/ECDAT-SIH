"""Bounded loading and validation of evaluation ground truth."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MAX_GROUND_TRUTH_ASSETS = 10_000


def load_ground_truth(repo_path: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    truth_path = Path(repo_path) / "ground_truth.json"
    if not truth_path.exists():
        return None, {"available": False, "message": "No ground_truth.json exists in the scanned repository"}
    try:
        truth = _read_truth(truth_path)
        _validate_truth(truth)
        return truth, None
    except (OSError, ValueError, TypeError, RecursionError) as exc:
        return None, {
            "available": False,
            "message": f"Ground truth is unreadable, invalid or exceeds 2 MiB: {exc}",
        }


def _read_truth(path: Path) -> dict[str, Any]:
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("oversized ground truth")
    truth = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(truth, dict):
        raise ValueError("ground truth is not a JSON object")
    return truth


def _validate_truth(truth: dict[str, Any]) -> None:
    assets = truth.get("assets")
    if not isinstance(assets, list):
        raise ValueError("missing or invalid 'assets' list")
    if len(assets) > MAX_GROUND_TRUTH_ASSETS:
        raise ValueError(f"ground truth exceeds {MAX_GROUND_TRUTH_ASSETS:,} assets")
    for item in assets:
        if not isinstance(item, dict):
            raise ValueError("asset entry is not an object")
        for key in ("component", "algorithm"):
            if not isinstance(item.get(key), str) or not item[key].strip():
                raise ValueError(f"asset missing valid '{key}'")
    for key in ("blind_spots", "alias_pairs", "cert_expectations"):
        if key in truth and not isinstance(truth[key], list):
            raise ValueError(f"'{key}' must be a list")
