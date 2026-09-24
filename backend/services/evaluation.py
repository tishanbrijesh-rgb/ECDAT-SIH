"""
Ground-truth evaluation for reproducible discovery-assurance metrics.

Two matching modes:

* **v1 (legacy)** — set-based ``(component, algorithm)`` matching, identical to
  the original ``evaluate_assets`` implementation.  Activated when
  ``ground_truth.json`` has no ``"evaluation_version"`` key (or the value is 1).

* **v2 (operation-level)** — one-to-one operation matching that considers
  algorithm family aliases, usage accuracy, key_size accuracy, and detects
  duplicate findings as false positives.  Activated when the ground truth
  contains ``"evaluation_version": 2`` or higher.

The public ``evaluate_assets`` entry point stays fully compatible: it accepts
the same arguments and returns the same top-level keys, enriched with
additional v2 metrics when applicable.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any

from backend.services.evaluation_models import EvaluatedOperation
from backend.services.ground_truth import load_ground_truth

# ---------------------------------------------------------------------------
# Internal data model
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Alias resolution
# ---------------------------------------------------------------------------

def _build_alias_map(alias_pairs: list[dict]) -> dict[str, str]:
    """Build ``algorithm → canonical_name`` mapping from ground-truth alias pairs."""
    alias_map: dict[str, str] = {}
    for pair in alias_pairs:
        algorithms = pair.get("algorithms", [])
        if len(algorithms) < 2:
            continue
        canonical = algorithms[0]
        for alias in algorithms:
            alias_map[alias] = canonical
    return alias_map


def _resolve_algorithm(raw: str, alias_map: dict[str, str]) -> str:
    """Return the canonical algorithm name, falling back to the raw value."""
    return alias_map.get(raw, raw)


# ---------------------------------------------------------------------------
# Evidence extraction — derives operation-level fields from correlator output
# ---------------------------------------------------------------------------

def _extract_component(asset: Any) -> str:
    """Derive component name from a correlated finding or raw asset."""
    if hasattr(asset, "evidence_json") and asset.evidence_json:
        return asset.evidence_json.get("component", "")
    if isinstance(asset, dict):
        ev = asset.get("evidence_json") or asset.get("evidence") or {}
        return ev.get("component", "")
    return ""


def _extract_algorithm(asset: Any) -> str:
    """Extract algorithm string."""
    if hasattr(asset, "algorithm"):
        return asset.algorithm
    if isinstance(asset, dict):
        return asset.get("algorithm", "")
    return ""


def _extract_usage(asset: Any) -> str:
    """Extract usage from correlated finding, walking evidence_list if needed."""
    if isinstance(asset, dict):
        # Direct field on correlated finding.
        usage = asset.get("usage")
        if usage:
            return str(usage).lower().strip()
        ev = asset.get("evidence_json") or {}
        usage = ev.get("usage")
        if usage:
            return str(usage).lower().strip()
        # Walk evidence_list for usage from individual evidence items.
        for item in (ev.get("evidence_list") or []):
            u = (item.get("evidence") or {}).get("usage")
            if u:
                return str(u).lower().strip()
    if hasattr(asset, "evidence_json") and asset.evidence_json:
        return _extract_usage({"evidence_json": asset.evidence_json})
    return "unknown"


def _normalise_usage(raw: str) -> str:
    """Map aliased usage names to canonical values."""
    return {"sign": "signature", "verify": "signature", "hash": "hashing",
            "key_exchange": "key_establishment"}.get(raw, raw)


def _extract_key_size(asset: Any) -> int | None:
    """Extract key_size from correlated finding, walking evidence chain."""
    if isinstance(asset, dict):
        ks = asset.get("key_size")
        if ks is not None:
            try:
                return int(ks)
            except (TypeError, ValueError):
                pass
        ev = asset.get("evidence_json") or {}
        ks = ev.get("key_size")
        if ks is not None:
            try:
                return int(ks)
            except (TypeError, ValueError):
                pass
        for item in (ev.get("evidence_list") or []):
            ks = (item.get("evidence") or {}).get("key_size")
            if ks is not None:
                try:
                    return int(ks)
                except (TypeError, ValueError):
                    continue
    if hasattr(asset, "evidence_json") and asset.evidence_json:
        return _extract_key_size({"evidence_json": asset.evidence_json})
    return None


def _extract_line(asset: Any) -> int | None:
    """Extract line number from evidence chain."""
    if isinstance(asset, dict):
        ev = asset.get("evidence_json") or {}
        for item in (ev.get("evidence_list") or []):
            line = (item.get("evidence") or {}).get("line")
            if line is not None:
                try:
                    return int(line)
                except (TypeError, ValueError):
                    continue
        line = ev.get("line")
        if line is not None:
            try:
                return int(line)
            except (TypeError, ValueError):
                pass
    if hasattr(asset, "evidence_json") and asset.evidence_json:
        return _extract_line({"evidence_json": asset.evidence_json})
    return None


def _extract_file(asset: Any) -> str:
    """Extract file path for grouping."""
    if isinstance(asset, dict):
        return asset.get("location", "")
    if hasattr(asset, "location"):
        return asset.location
    return ""


def _iter_sources(asset: Any) -> list[str]:
    """Iterate over source names from an asset."""
    if isinstance(asset, dict):
        src = asset.get("source")
        if isinstance(src, list):
            return src
        if isinstance(src, str):
            return [src]
    if hasattr(asset, "source"):
        val = asset.source
        if isinstance(val, list):
            return val
        if isinstance(val, str):
            return [val]
    return []


# ---------------------------------------------------------------------------
# Hungarian algorithm for optimal one-to-one matching
# ---------------------------------------------------------------------------

def _hungarian_match(
    expected: list[EvaluatedOperation],
    actual: list[EvaluatedOperation],
    score_fn: Callable[[EvaluatedOperation, EvaluatedOperation], float],
) -> tuple[list[tuple[int, int]], set[int], set[int]]:
    """Maximum-score bipartite matching via Hungarian algorithm.

    Returns ``(pairs, unmatched_expected_indices, unmatched_actual_indices)``.
    Each pair is ``(expected_index, actual_index)``.
    """
    if not expected or not actual:
        return [], set(range(len(expected))), set(range(len(actual)))

    # Ensure rows <= columns for the standard Hungarian formulation.
    swapped = len(expected) > len(actual)
    rows, columns = (actual, expected) if swapped else (expected, actual)
    row_count, column_count = len(rows), len(columns)

    # Build cost matrix (negated scores for minimisation).
    costs = [
        [-score_fn(rows[r], columns[c]) for c in range(column_count)]
        for r in range(row_count)
    ]

    # Kuhn-Munkres implementation.
    u = [0] * (row_count + 1)
    v = [0] * (column_count + 1)
    p = [0] * (column_count + 1)
    way = [0] * (column_count + 1)

    for row in range(1, row_count + 1):
        p[0] = row
        column_zero = 0
        minimum = [float("inf")] * (column_count + 1)
        used = [False] * (column_count + 1)
        while True:
            used[column_zero] = True
            current_row = p[column_zero]
            delta = float("inf")
            next_column = 0
            for column in range(1, column_count + 1):
                if used[column]:
                    continue
                current = costs[current_row - 1][column - 1] - u[current_row] - v[column]
                if current < minimum[column]:
                    minimum[column] = current
                    way[column] = column_zero
                if minimum[column] < delta:
                    delta = minimum[column]
                    next_column = column
            for column in range(column_count + 1):
                if used[column]:
                    u[p[column]] += delta
                    v[column] -= delta
                else:
                    minimum[column] -= delta
            column_zero = next_column
            if p[column_zero] == 0:
                break
        while True:
            next_column = way[column_zero]
            p[column_zero] = p[next_column]
            column_zero = next_column
            if column_zero == 0:
                break

    # Extract pairs and identify unmatched.
    pairs: list[tuple[int, int]] = []
    for column in range(1, column_count + 1):
        if p[column] == 0:
            continue
        row_idx = p[column] - 1
        if swapped:
            pairs.append((column - 1, row_idx))
        else:
            pairs.append((row_idx, column - 1))

    all_expected = set(range(len(expected)))
    all_actual = set(range(len(actual)))
    paired_expected = {e for e, _ in pairs}
    paired_actual = {a for _, a in pairs}
    return pairs, all_expected - paired_expected, all_actual - paired_actual


# ---------------------------------------------------------------------------
# Operation-level matching
# ---------------------------------------------------------------------------

def _operation_match_score(
    expected: EvaluatedOperation,
    actual: EvaluatedOperation,
) -> float:
    """Score a potential (expected, actual) pair for the Hungarian algorithm.

    One metadata match outweighs every possible usage tie-break to ensure
    the optimizer finds the globally optimal pairing.
    """
    usage_match = expected.usage == actual.usage
    key_size_match = expected.key_size == actual.key_size
    if expected.component != actual.component:
        return -2  # cross-component pairs are never valid matches
    either_match = usage_match or key_size_match
    bonus = int(usage_match and key_size_match)
    return -1 + int(either_match) + int(usage_match) * 100 + bonus


def _match_operations(
    expected: list[EvaluatedOperation],
    actual: list[EvaluatedOperation],
) -> tuple[
    list[tuple[EvaluatedOperation, EvaluatedOperation]],
    list[EvaluatedOperation],
    list[EvaluatedOperation],
    dict[str, int],
]:
    """Match expected and actual operations one-to-one.

    Returns ``(matched_pairs, missed, unexpected, metadata_scores)``.
    """
    pairs, missed_idx, unexpected_idx = _hungarian_match(
        expected, actual, _operation_match_score,
    )

    matched: list[tuple[EvaluatedOperation, EvaluatedOperation]] = []
    missed = [expected[i] for i in sorted(missed_idx)]
    unexpected = [actual[i] for i in sorted(unexpected_idx)]

    usage_ok = key_ok = metadata_pair_ok = 0
    known_keys = known_keys_ok = 0

    for e_idx, a_idx in pairs:
        exp = expected[e_idx]
        act = actual[a_idx]
        # Component mismatch: reject the pair — treat as missed + unexpected.
        if exp.component != act.component:
            missed.append(exp)
            unexpected.append(act)
            continue
        exp._matched = True
        act._matched = True
        exp._pair_index = a_idx
        matched.append((exp, act))
        if exp.usage == act.usage:
            usage_ok += 1
        if exp.key_size == act.key_size:
            key_ok += 1
        if exp.usage == act.usage and exp.key_size == act.key_size:
            metadata_pair_ok += 1
        if exp.key_size is not None:
            known_keys += 1
            if exp.key_size == act.key_size:
                known_keys_ok += 1

    # Missed expected items still count toward known key_size denominator.
    for exp in missed:
        if exp.key_size is not None:
            known_keys += 1

    metadata_scores = {
        "usage_correct": usage_ok,
        "key_size_correct": key_ok,
        "metadata_pair_correct": metadata_pair_ok,
        "known_key_size_correct": known_keys_ok,
        "known_key_size_denominator": known_keys,
    }
    return matched, missed, unexpected, metadata_scores


# ---------------------------------------------------------------------------
# Ground truth loading and validation
# ---------------------------------------------------------------------------

def _load_ground_truth(
    repo_path: str,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Compatibility wrapper around the bounded ground-truth loader."""
    return load_ground_truth(repo_path)


def _is_v2(truth: dict) -> bool:
    """Return True if the ground truth requests operation-level evaluation."""
    return int(truth.get("evaluation_version", 1)) >= 2


# ---------------------------------------------------------------------------
# V1 evaluator (legacy, unmodified behaviour)
# ---------------------------------------------------------------------------

def _evaluate_v1(assets: list[Any], truth: dict) -> dict[str, Any]:
    """Original set-based ``(component, algorithm)`` evaluator."""
    expected: set[tuple[str, str]] = set()
    for item in truth["assets"]:
        expected.add((item["component"], item["algorithm"]))

    actual: set[tuple[str, str]] = set()
    source_actual: dict[str, set[tuple[str, str]]] = {}
    for asset in assets:
        component = _extract_component(asset) or Path(
            _extract_file(asset) or "."
        ).parent.name
        key = (component, _extract_algorithm(asset))
        actual.add(key)
        for source in _iter_sources(asset):
            source_actual.setdefault(source, set()).add(key)

    true_positive = expected & actual
    false_positive = actual - expected
    false_negative = expected - actual
    precision = len(true_positive) / len(actual) if actual else 0.0
    recall = len(true_positive) / len(expected) if expected else 1.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )

    per_source: dict[str, dict[str, Any]] = {}
    for source, findings in source_actual.items():
        tp = len(findings & expected)
        per_source[source] = {
            "findings": len(findings),
            "precision": round(tp / len(findings), 4) if findings else 0.0,
            "recall": round(tp / len(expected), 4) if expected else 1.0,
        }

    return {
        "granularity": "component_algorithm",
        "evaluation_version": 1,
        "limitations": [
            "These metrics do not validate operation identity or usage correctness"
        ],
        "available": True,
        "expected": len(expected),
        "found": len(actual),
        "operation_findings": len(assets),
        "true_positives": len(true_positive),
        "false_positives": len(false_positive),
        "false_negatives": len(false_negative),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "missed": [
            {"component": c, "algorithm": a}
            for c, a in sorted(false_negative)
        ],
        "unexpected": [
            {"component": c, "algorithm": a}
            for c, a in sorted(false_positive)
        ],
        "per_source": per_source,
        "declared_blind_spots": truth.get("blind_spots", []),
    }


# ---------------------------------------------------------------------------
# V2 evaluator (operation-level)
# ---------------------------------------------------------------------------

def _build_expected_operations(
    truth: dict, alias_map: dict[str, str]
) -> list[EvaluatedOperation]:
    """Convert ground truth assets to expected operations with alias resolution."""
    operations: list[EvaluatedOperation] = []
    for item in truth["assets"]:
        algo = alias_map.get(item["algorithm"], item["algorithm"])
        operations.append(
            EvaluatedOperation(
                original_algorithm=item["algorithm"],
                algorithm=algo,
                component=item["component"],
                usage=_normalise_usage(item.get("usage", "unknown")),
                key_size=item.get("key_size"),
                line=item.get("line"),
                file=item.get("file", ""),
                confidence=item.get("confidence", 1.0),
            )
        )
    return operations


def _build_actual_operations(assets: list[Any]) -> list[EvaluatedOperation]:
    """Convert correlated scan findings to actual operations."""
    operations: list[EvaluatedOperation] = []
    for asset in assets:
        algo = _extract_algorithm(asset)
        if not algo:
            continue
        confidence = 0.82
        if isinstance(asset, dict):
            confidence = asset.get("confidence", 0.82)
        elif hasattr(asset, "confidence"):
            confidence = asset.confidence
        operations.append(
            EvaluatedOperation(
                original_algorithm=algo,
                algorithm=algo,
                component=(
                    _extract_component(asset)
                    or Path(_extract_file(asset) or ".").parent.name
                    or "repository-root"
                ),
                usage=_normalise_usage(_extract_usage(asset)),
                key_size=_extract_key_size(asset),
                line=_extract_line(asset),
                file=_extract_file(asset),
                confidence=confidence,
            )
        )
    return operations


def _evaluate_v2(
    assets: list[Any],
    truth: dict,
) -> dict[str, Any]:
    """Operation-level evaluator with alias-aware matching and metadata scoring."""
    alias_map = _build_alias_map(truth.get("alias_pairs", []))

    # Build expected and actual operations with alias resolution.
    expected = _build_expected_operations(truth, alias_map)
    actual = _build_actual_operations(assets)

    # One-to-one operation matching.
    matched, missed, unexpected, meta_scores = _match_operations(
        expected, actual
    )

    tp = len(matched)
    fp = len(unexpected)
    fn = len(missed)
    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision is not None and recall is not None and precision + recall
        else None
    )

    # Per-source breakdown.
    source_actual: dict[str, list[EvaluatedOperation]] = defaultdict(list)
    actual_index = 0
    for asset in assets:
        for source in _iter_sources(asset):
            if actual_index < len(actual):
                source_actual[source].append(actual[actual_index])
        actual_index += 1

    per_source: dict[str, dict[str, Any]] = {}
    for source, source_ops in source_actual.items():
        matched_in_source = sum(1 for op in source_ops if op._matched)
        per_source[source] = {
            "findings": len(source_ops),
            "true_positives": matched_in_source,
            "precision": (
                round(matched_in_source / len(source_ops), 4) if source_ops else 0.0
            ),
            "recall": (
                round(matched_in_source / len(expected), 4) if expected else 1.0
            ),
        }

    # Certificate evaluation.
    cert_eval = _evaluate_certificates(
        assets, truth.get("cert_expectations", [])
    )

    total_expected = len(expected)

    return {
        "granularity": "operation",
        "evaluation_version": 2,
        "available": True,
        "expected": total_expected,
        "found": len(actual),
        "operation_findings": len(actual),
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "precision": round(precision, 4) if precision is not None else None,
        "recall": round(recall, 4) if recall is not None else None,
        "f1": round(f1, 4) if f1 is not None else None,
        "usage_correct": meta_scores["usage_correct"],
        "usage_accuracy_over_expected": (
            round(meta_scores["usage_correct"] / total_expected, 4)
            if total_expected
            else None
        ),
        "known_key_size_correct": meta_scores["known_key_size_correct"],
        "known_key_size_accuracy_over_expected": (
            round(meta_scores["known_key_size_correct"] / meta_scores["known_key_size_denominator"], 4)
            if meta_scores["known_key_size_denominator"]
            else None
        ),
        "metadata_pair_correct": meta_scores["metadata_pair_correct"],
        "metadata_pair_accuracy_over_expected": (
            round(meta_scores["metadata_pair_correct"] / total_expected, 4)
            if total_expected
            else None
        ),
        "matched_operations": tp,
        "duplicate_findings_as_fp": fp,
        "missed": [
            {
                "component": op.component,
                "algorithm": op.original_algorithm,
                "usage": op.usage,
                "line": op.line,
            }
            for op in sorted(
                missed, key=lambda o: (o.component, o.algorithm, o.line or 0)
            )
        ],
        "unexpected": [
            {
                "component": op.component,
                "algorithm": op.original_algorithm,
                "usage": op.usage,
                "line": op.line,
            }
            for op in sorted(
                unexpected, key=lambda o: (o.component, o.algorithm, o.line or 0)
            )
        ],
        "per_source": per_source,
        "certificate_evaluation": cert_eval,
        "declared_blind_spots": truth.get("blind_spots", []),
    }


# ---------------------------------------------------------------------------
# Certificate evaluation
# ---------------------------------------------------------------------------

def _evaluate_certificates(
    assets: list[Any],
    expectations: list[dict],
) -> dict[str, Any] | None:
    """Evaluate certificate findings against cert_expectations."""
    if not expectations:
        return None

    # Collect certificate findings.
    cert_findings: list[dict[str, Any]] = []
    for asset in assets:
        if "cert" not in _iter_sources(asset):
            continue
        evidence = _get_evidence(asset)
        cert_info = {
            "algorithm": _extract_algorithm(asset),
            "key_size": evidence.get("key_size"),
            "not_after": evidence.get("not_after", ""),
            "not_before": _parse_date(evidence.get("not_before", "")),
            "component": _extract_component(asset),
            "subject_cn": evidence.get("subject_cn", ""),
            "serial_number": evidence.get("serial_number", ""),
        }
        cert_findings.append(cert_info)

    matched = 0
    mismatches: list[dict] = []

    for exp in expectations:
        component = exp.get("component", "")
        best = _find_best_cert_match(cert_findings, component)
        if best is None:
            mismatches.append(
                {
                    "component": component,
                    "issue": "certificate_not_found",
                    "expected_key_size": exp.get("key_size"),
                }
            )
            continue
        cert_issues: list[str] = []
        if best["key_size"] != exp.get("key_size"):
            cert_issues.append(
                f"key_size mismatch: expected {exp.get('key_size')}, "
                f"found {best['key_size']}"
            )
        not_after = exp.get("not_after", "")
        if not_after and best.get("not_after") != not_after:
            cert_issues.append(
                f"not_after mismatch: expected {not_after}, "
                f"found {best.get('not_after', 'N/A')}"
            )
        if cert_issues:
            mismatches.append(
                {
                    "component": component,
                    "issue": "; ".join(cert_issues),
                    "found": best,
                }
            )
        else:
            matched += 1

    total = len(expectations)
    return {
        "total_expected": total,
        "matched": matched,
        "mismatches": mismatches,
        "certificate_accuracy": round(matched / total, 4) if total else None,
    }


def _get_evidence(asset: Any) -> dict[str, Any]:
    """Extract the evidence dict from an asset."""
    if isinstance(asset, dict):
        ev = asset.get("evidence_json") or asset.get("evidence") or {}
        if isinstance(ev, dict):
            return ev
    if hasattr(asset, "evidence_json") and isinstance(asset.evidence_json, dict):
        return asset.evidence_json
    return {}


def _parse_date(value: str) -> str:
    """Normalise a date string for comparison."""
    if not value:
        return ""
    return value.split("T")[0] if "T" in value else value


def _find_best_cert_match(
    findings: list[dict[str, Any]],
    component: str,
) -> dict[str, Any] | None:
    """Find the best matching certificate finding for a component."""
    # Exact component match first.
    for finding in findings:
        if finding.get("component", "") == component:
            return finding
    # Fallback: match by file name.
    target_name = Path(component).name.lower()
    for finding in findings:
        if Path(finding.get("component", "")).name.lower() == target_name:
            return finding
    # Fallback: partial match.
    for finding in findings:
        if target_name in finding.get("component", "").lower():
            return finding
    return None


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def evaluate_assets(assets: list[Any], repo_path: str) -> dict[str, Any]:
    """Evaluate scanned assets against ground_truth.json.

    Args:
        assets: List of correlated CryptoAsset objects or finding dicts.
        repo_path: Path to the scanned repository (must contain ground_truth.json).

    Returns:
        Evaluation result dict with metrics.  Keys vary by evaluation version:
        v1 returns component_algorithm-level metrics; v2 returns operation-level
        metrics with usage/key_size accuracy and certificate evaluation.
    """
    truth, error = _load_ground_truth(repo_path)
    if error is not None:
        return error

    if _is_v2(truth):
        result = _evaluate_v2(assets, truth)
    else:
        result = _evaluate_v1(assets, truth)

    result.setdefault("declared_blind_spots", truth.get("blind_spots", []))
    return result
