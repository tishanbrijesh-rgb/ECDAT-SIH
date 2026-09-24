"""Canonical operation-v3 evidence correlator."""

from __future__ import annotations

import hashlib
import json
import os
from collections import defaultdict
from copy import deepcopy
from typing import Any

# ── V3 post-processing over v2 output ──────────────────────────────────────

def _span_anchor(finding: dict[str, Any]) -> str:
    """Compute a span anchor resilient to small line shifts (within 3 lines).

    Normalizes line_start to the nearest multiple-of-3 bucket so that
    findings at lines 1-3 share an anchor, lines 4-6 share another, etc.
    Column is preserved as-is.
    """
    location = os.path.normpath(finding.get("location", ""))
    evidence_list = finding.get("evidence_list", [])
    if evidence_list:
        span = (evidence_list[0].get("span") or {})
        line_start = span.get("line_start")
        col_start = span.get("column_start")
        if line_start is not None:
            line_number = max(1, int(line_start))
            norm_line = ((line_number - 1) // 3) * 3 + 1
            if col_start is not None:
                return f"{location}:L{norm_line}:C{col_start}"
            return f"{location}:L{norm_line}"
    return f"{location}:unknown"


# ── Canonical v3 correlator helpers ─────────────────────────────────────────

def _v3_semantic_anchor(record: dict[str, Any]) -> str | None:
    details = record.get("evidence") or {}
    op_name = (details.get("operation_name")
               or details.get("method_name")
               or details.get("function_name"))
    if op_name:
        return f"op:{op_name}"
    ctx = details.get("function") or details.get("class") or details.get("method")
    if ctx:
        return f"ctx:{ctx}"
    return None


def _v3_span_identity(record: dict[str, Any]) -> dict[str, Any]:
    span = record.get("span") or {}
    return {
        "file": os.path.normpath(record.get("location", "")),
        "line_start": span.get("line_start"),
        "column_start": span.get("column_start"),
        "semantic_anchor": _v3_semantic_anchor(record),
    }


def _v3_spans_nearby(a: dict[str, Any], b: dict[str, Any], threshold: int = 5) -> bool:
    if a.get("file") != b.get("file"):
        return False
    la, lb = a.get("line_start"), b.get("line_start")
    if la is None or lb is None:
        return False
    return abs(int(la) - int(lb)) <= threshold


def _v3_spans_match(a: dict[str, Any], b: dict[str, Any]) -> bool:
    if a.get("file") != b.get("file"):
        return False
    la, lb = a.get("line_start"), b.get("line_start")
    if la is not None and lb is not None and abs(int(la) - int(lb)) > 5:
        return False
    ca, cb = a.get("column_start"), b.get("column_start")
    return not (ca is not None and cb is not None and int(ca) != int(cb))


def _v3_group_key(span_id: dict[str, Any], algorithm: str, evidence_kind: str) -> tuple:
    return (
        span_id.get("file", ""),
        algorithm,
        span_id.get("line_start"),
        span_id.get("column_start"),
        span_id.get("semantic_anchor") or "",
        evidence_kind,
    )


def _v3_cross_kind_key(span_id: dict[str, Any], algorithm: str) -> tuple:
    return (
        span_id.get("file", ""),
        algorithm,
        span_id.get("line_start"),
        span_id.get("column_start"),
        span_id.get("semantic_anchor") or "",
    )


def _v3_moved_line_note(span_id: dict[str, Any], record: dict[str, Any]) -> str:
    if span_id.get("line_start") is None:
        return ""
    parts = [f"line={span_id['line_start']}", f"algo={record.get('algorithm', '')}"]
    col = span_id.get("column_start")
    if col is not None:
        parts.append(f"col={col}")
    sem = span_id.get("semantic_anchor")
    if sem:
        parts.append(f"ctx={sem}")
    return "[" + ";".join(parts) + "]"


def _v3_find_cross_collector_matches(
    target: dict[str, Any],
    candidates: list[dict[str, Any]],
    target_kind: str,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for cand in candidates:
        cand_kind = cand.get("_v3_evidence_kind", "unknown")
        same_kind = target_kind == cand_kind
        nearby = _v3_spans_nearby(target["_v3_span_id"], cand["_v3_span_id"])

        if same_kind and nearby:
            results.append({"candidate": cand, "confidence": 1.0, "merge": True, "ambiguous": False})
        elif not same_kind and nearby:
            results.append({"candidate": cand, "confidence": 0.7, "merge": False, "ambiguous": False})
        elif same_kind and not nearby:
            results.append({"candidate": cand, "confidence": 0.0, "merge": False, "ambiguous": False})
        else:
            results.append({"candidate": cand, "confidence": 0.3, "merge": False, "ambiguous": True})
    return results


def _v3_context(evidence: dict[str, Any]) -> dict[str, Any]:
    details = evidence.get("evidence") or {}
    ek = (details.get("evidence_kind") or evidence.get("evidence_kind") or "unknown")
    return {
        "usage": details.get("usage") or "unknown",
        "library": details.get("library") or details.get("package") or details.get("groupId") or "",
        "protocol": details.get("protocol") or "",
        "key_size": details.get("key_size"),
        "operation_id": details.get("operation_id"),
        "evidence_kind": ek,
    }


def _v3_usage(record: dict[str, Any]) -> str:
    value = str(_v3_context(record)["usage"]).strip().lower()
    value = {"sign": "signature", "verify": "signature", "hash": "hashing",
             "key_exchange": "key_establishment"}.get(value, value)
    return value if value in {"signature", "encryption", "hashing", "key_establishment", "tls"} else "unknown"


def _v3_component(location: str) -> str:
    from pathlib import Path
    path = Path(os.path.normpath(location))
    parts = [part for part in path.parts if part not in {path.anchor, "", "."}]
    for marker in ("test-repo", "repositories", "apps", "services"):
        if marker in parts:
            index = parts.index(marker)
            if index + 1 < len(parts):
                return parts[index + 1]
    return path.parent.name or "repository-root"


def _prepare_records(evidence_dict: dict) -> list[dict[str, Any]]:
    records = sorted(
        [deepcopy(record) for evidences in evidence_dict.values() for record in evidences],
        key=lambda record: (
            json.dumps({k: v for k, v in record.items() if k != "asset_id"},
                       sort_keys=True, default=str),
            str(record.get("asset_id", "")),
        ),
    )

    for record in records:
        record.setdefault("_v3_span_id", _v3_span_identity(record))
        record.setdefault("_v3_evidence_kind",
                          _v3_context(record).get("evidence_kind", "unknown"))
        record.setdefault("_v3_component",
                          _v3_component(record.get("location", "")))
        record.setdefault("_v3_usage", _v3_usage(record))
    return records


def _group_records(records: list[dict[str, Any]]) -> dict[tuple, list[dict[str, Any]]]:
    grouped: dict[tuple, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        sp = record["_v3_span_id"]
        key = _v3_group_key(
            sp, record.get("algorithm", "unknown"), record["_v3_evidence_kind"]
        )
        grouped[key].append(record)
    return grouped


def _cross_kind_buckets(grouped: dict[tuple, list[dict[str, Any]]]) -> dict[tuple, list[tuple]]:
    cross_kind_buckets: dict[tuple, list[tuple]] = defaultdict(list)
    for key in grouped:
        ck = _v3_cross_kind_key(
            {"file": key[0], "line_start": key[2], "column_start": key[3],
             "semantic_anchor": key[4]},
            key[1],
        )
        cross_kind_buckets[ck].append(key)
    return cross_kind_buckets


def _cross_kind_links(buckets: dict[tuple, list[tuple]]) -> dict[tuple, list[str]]:
    cross_kind_links: dict[tuple, list[str]] = defaultdict(list)
    for primary_keys in buckets.values():
        kinds = {pk[5] for pk in primary_keys}
        if len(kinds) > 1:
            for pk in primary_keys:
                cross_kind_links[pk] = [k for k in kinds if k != pk[5]]
    return cross_kind_links


def _ambiguous_match_payload(match: dict[str, Any]) -> dict[str, Any]:
    candidate = match["candidate"]
    span = candidate["_v3_span_id"]
    return {
        "candidate_algorithm": candidate.get("algorithm", "unknown"),
        "candidate_evidence_kind": candidate.get("_v3_evidence_kind", "unknown"),
        "candidate_span": {
            "file": span.get("file", ""),
            "line_start": span.get("line_start"),
            "column_start": span.get("column_start"),
            "semantic_anchor": span.get("semantic_anchor"),
        },
        "confidence": match["confidence"],
        "merge_flag": match["merge"],
    }


def _ambiguous_matches(
    grouped: dict[tuple, list[dict[str, Any]]],
) -> dict[tuple, list[dict[str, Any]]]:
    ambiguous_matches: dict[tuple, list[dict[str, Any]]] = defaultdict(list)
    file_algorithm_groups: dict[tuple[str, str], list[tuple]] = defaultdict(list)
    for primary_key in grouped:
        file_algorithm_groups[(primary_key[0], primary_key[1])].append(primary_key)
    for primary_keys in file_algorithm_groups.values():
        if len(primary_keys) < 2:
            continue
        bucket_records: list[dict[str, Any]] = []
        for pk in primary_keys:
            bucket_records.extend(grouped[pk])

        for i, target in enumerate(bucket_records):
            others = [r for j, r in enumerate(bucket_records) if j != i]
            matches = _v3_find_cross_collector_matches(
                target, others, target["_v3_evidence_kind"]
            )
            uncertain = [m for m in matches
                         if m["ambiguous"] or (0.0 < m["confidence"] < 0.7)]
            if uncertain:
                target_key = _v3_group_key(
                    target["_v3_span_id"],
                    target.get("algorithm", "unknown"),
                    target["_v3_evidence_kind"],
                )
                for m in uncertain:
                    ambiguous_matches[target_key].append(_ambiguous_match_payload(m))
    return ambiguous_matches


def _evidence_summary(
    evidences: list[dict[str, Any]],
) -> tuple[list[str], dict[str, float], list[dict[str, Any]]]:
    sources: list[str] = []
    confidence_by_source: dict[str, float] = {}
    unique_evidence: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in evidences:
        source = item.get("source", "unknown")
        if source not in sources:
            sources.append(source)
        confidence_by_source[source] = max(
            confidence_by_source.get(source, 0.0), float(item.get("confidence", 0.0))
        )
        fingerprint = json.dumps(item, sort_keys=True, default=str)
        if fingerprint not in seen:
            seen.add(fingerprint)
            unique_evidence.append(item)
    return sources, confidence_by_source, unique_evidence


def _context_value(
    field: str,
    default: Any,
    contexts: list[dict[str, Any]],
    conflicts: dict[str, list],
) -> Any:
    values = sorted({
        json.dumps(ctx[field], sort_keys=True, default=str)
        for ctx in contexts if ctx[field] not in (None, "")
    })
    parsed = [json.loads(value) for value in values]
    if field == "key_size" and any(type(value) is not int or value <= 0 for value in parsed):
        conflicts[field] = parsed
        return default
    if len(parsed) > 1:
        conflicts[field] = parsed
    return parsed[0] if len(parsed) == 1 else default


def _operation_anchor(line_start: Any, column_start: Any, semantic_anchor: Any) -> str:
    parts = [f"line:{line_start}"]
    if column_start is not None:
        parts.append(f"col:{column_start}")
    if semantic_anchor:
        parts.append(f"ctx:{semantic_anchor}")
    return ":".join(parts)


def _build_finding(
    identity: tuple,
    evidences: list[dict[str, Any]],
    linked_kinds: list[str],
    ambiguous: list[dict[str, Any]],
) -> dict[str, Any]:
    file_, algo, line_start, column_start, semantic_anchor, evidence_kind = identity
    usage = evidences[0]["_v3_usage"]
    sources, confidence_by_source, unique_evidence = _evidence_summary(evidences)
    contexts = [_v3_context(item) for item in evidences]
    moved_line_note = _v3_moved_line_note(
        {"file": file_, "line_start": line_start, "column_start": column_start,
         "semantic_anchor": semantic_anchor}, evidences[0]
    )
    preferred = next(
        (item for item in evidences if item.get("source") in {"ast", "cert", "rule"}),
        evidences[0],
    )
    category = {
        "signature": "signature", "hashing": "hash", "key_establishment": "key_exchange",
        "tls": "protocol", "encryption": "encryption", "key_derivation": "kdf",
    }.get(usage, preferred.get("category", "unknown"))
    conflicts: dict[str, list] = {}
    library = _context_value("library", "", contexts, conflicts)
    protocol = _context_value("protocol", "", contexts, conflicts)
    key_size = _context_value("key_size", None, contexts, conflicts)
    confidence = round(max(
        0.0,
        sum(confidence_by_source.values()) / max(len(confidence_by_source), 1)
        - 0.1 * len(ambiguous),
    ), 2)
    logical_id = hashlib.sha256(json.dumps([
        "operation-v3", file_, algo, line_start, column_start,
        semantic_anchor or "", evidence_kind, moved_line_note,
    ]).encode()).hexdigest()[:16]
    return {
        "logical_asset_id": logical_id, "component": _v3_component(file_),
        "algorithm": algo, "category": category, "location": preferred.get("location", ""),
        "sources": sorted(sources), "confidence_by_source": confidence_by_source,
        "confidence": confidence, "conflict": bool(conflicts), "conflicting_operations": [],
        "operation_anchor": _operation_anchor(line_start, column_start, semantic_anchor),
        "correlation_version": "operation-v3", "context_conflicts": conflicts,
        "evidence_list": unique_evidence, "source_count": len(sources), "usage": usage,
        "evidence_kind": evidence_kind, "library": library, "protocol": protocol,
        "key_size": key_size,
        "span": {"file": file_, "line_start": line_start, "column_start": column_start,
                 "semantic_anchor": semantic_anchor, "moved_line_note": moved_line_note or None},
        "cross_kind_links": linked_kinds, "ambiguous_matches": ambiguous,
    }


def correlate(evidence_dict: dict) -> list[dict[str, Any]]:
    """V3 correlator with normalized spans, ambiguity, and cross-kind linking."""
    grouped = _group_records(_prepare_records(evidence_dict))
    buckets = _cross_kind_buckets(grouped)
    links = _cross_kind_links(buckets)
    ambiguous = _ambiguous_matches(grouped)
    findings: list[dict[str, Any]] = []
    for identity, evidences in sorted(grouped.items()):
        findings.append(_build_finding(
            identity, evidences, links.get(identity, []), ambiguous.get(identity, [])
        ))
    return findings


# Backward-compatible name; both public entry points are the same function.
correlate_v3 = correlate
