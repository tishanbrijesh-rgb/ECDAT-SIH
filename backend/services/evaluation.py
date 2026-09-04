"""Ground-truth evaluation for reproducible discovery-assurance metrics."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

def evaluate_assets(assets: list[Any], repo_path: str) -> dict[str, Any]:
    truth_path = Path(repo_path) / "ground_truth.json"
    if not truth_path.exists():
        return {"available": False, "message": "No ground_truth.json exists in the scanned repository"}
    try:
        if truth_path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError("oversized ground truth")
        truth = json.loads(truth_path.read_text(encoding="utf-8"))
        if not isinstance(truth, dict) or not isinstance(truth.get("assets"), list):
            raise ValueError("invalid ground truth")
        expected = set()
        for item in truth["assets"]:
            if not isinstance(item, dict) or any(
                not isinstance(item.get(key), str) or not item[key].strip()
                for key in ("component", "algorithm")
            ):
                raise ValueError("invalid asset")
            expected.add((item["component"], item["algorithm"]))
        if not isinstance(truth.get("blind_spots", []), list):
            raise ValueError("invalid blind spots")
    except (OSError, ValueError, TypeError, RecursionError):
        return {"available": False, "message": "Ground truth is unreadable, invalid or exceeds 2 MiB"}
    actual = set()
    source_actual: dict[str, set[tuple[str, str]]] = {}
    for asset in assets:
        component = (asset.evidence_json or {}).get("component") or Path(asset.location).parent.name
        key = (component, asset.algorithm)
        actual.add(key)
        for source in asset.source or []:
            source_actual.setdefault(source, set()).add(key)
    true_positive = expected & actual
    false_positive = actual - expected
    false_negative = expected - actual
    precision = len(true_positive) / len(actual) if actual else 0.0
    recall = len(true_positive) / len(expected) if expected else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    per_source = {}
    for source, findings in source_actual.items():
        tp = len(findings & expected)
        per_source[source] = {
            "findings": len(findings),
            "precision": round(tp / len(findings), 4) if findings else 0.0,
            "recall": round(tp / len(expected), 4) if expected else 1.0,
        }
    return {
        "granularity": "component_algorithm",
        "limitations": ["These metrics do not validate operation identity or usage correctness"],
        "operation_findings": len(assets),
        "available": True, "expected": len(expected), "found": len(actual),
        "true_positives": len(true_positive), "false_positives": len(false_positive),
        "false_negatives": len(false_negative), "precision": round(precision, 4),
        "recall": round(recall, 4), "f1": round(f1, 4),
        "missed": [{"component": c, "algorithm": a} for c, a in sorted(false_negative)],
        "unexpected": [{"component": c, "algorithm": a} for c, a in sorted(false_positive)],
        "per_source": per_source, "declared_blind_spots": truth.get("blind_spots", []),
    }
