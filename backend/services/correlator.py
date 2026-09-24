"""Logical evidence graph builder for ECDAT discovery assurance."""
from __future__ import annotations

import hashlib
import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any

from backend.services.correlator_v3 import correlate as correlate_v3


def _component(location: str) -> str:
    path = Path(os.path.normpath(location))
    parts = [part for part in path.parts if part not in {path.anchor, "", "."}]
    for marker in ("test-repo", "repositories", "apps", "services"):
        if marker in parts:
            index = parts.index(marker)
            if index + 1 < len(parts):
                return parts[index + 1]
    return path.parent.name or "repository-root"

def _context(evidence: dict[str, Any]) -> dict[str, Any]:
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


def _usage(record: dict[str, Any]) -> str:
    value = str(_context(record)["usage"]).strip().lower()
    value = {"sign": "signature", "verify": "signature", "hash": "hashing",
             "key_exchange": "key_establishment"}.get(value, value)
    return value if value in {"signature", "encryption", "hashing", "key_establishment", "tls"} else "unknown"


def _operation(record: dict[str, Any]) -> tuple[str, str]:
    """No inference across files or between unlocated evidence and operations."""
    details = record.get("evidence") or {}
    span = record.get("span") or {}
    location = os.path.normpath(record.get("location", ""))
    if details.get("operation_id"):
        anchor = "id:" + str(details["operation_id"])
    elif span.get("line_start") is not None:
        anchor = "line:" + str(span["line_start"])
        if span.get("column_start") is not None:
            anchor += ":column:" + str(span["column_start"])
    else:
        # Preserve distinct unlocated observations; UUIDs are not identity.
        anchor = "evidence:" + hashlib.sha256(json.dumps(details, sort_keys=True, default=str).encode()).hexdigest()[:16]
    return location, anchor

def correlate(evidence_dict: dict, mode: str = "v2") -> list[dict[str, Any]]:
    """Correlate only matching file/operation/algorithm/explicit-usage evidence.

    mode="v2" (default): exact line_start grouping — backward compatible.
    mode="v3": normalized span identity, cross-collector ambiguity, cross-kind
              linking, moved-line annotations, and ambiguous_matches tracking.
    """
    if mode == "v2":
        return _correlate_v2(evidence_dict)
    if mode == "v3":
        return correlate_v3(evidence_dict)
    raise ValueError(f"Unknown correlator mode: {mode!r}. Use 'v2' or 'v3'.")


# ── V2 (unchanged) ──────────────────────────────────────────────────────────

def _correlate_v2(evidence_dict: dict) -> list[dict[str, Any]]:
    """Original v2 correlator — exact line_start grouping.  Unchanged."""
    records = sorted([record for evidences in evidence_dict.values() for record in evidences],
                     key=lambda record: (json.dumps({k: v for k, v in record.items() if k != "asset_id"},
                                                    sort_keys=True, default=str), str(record.get("asset_id", ""))))
    operation_categories: dict[tuple[str, str], dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for record in records:
        # A package supporting several primitives is not an ambiguous runtime
        # operation. Conflict detection applies to direct collector evidence.
        if record.get("source") != "dep":
            operation_categories[_operation(record)][record.get("category", "unknown")].add(
                record.get("algorithm", "unknown")
            )
    component_strong_algorithms: dict[str, set[str]] = defaultdict(set)
    for record in records:
        if record.get("source") != "dep":
            component_strong_algorithms[_component(record.get("location", ""))].add(
                record.get("algorithm", "unknown")
            )
    grouped: dict[tuple[str, str, str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        component = _component(record.get("location", ""))
        algo = record.get("algorithm", "unknown")
        ek = _context(record).get("evidence_kind", "unknown")
        if (
            record.get("source") == "dep"
            and component_strong_algorithms[component]
            and algo not in component_strong_algorithms[component]
        ):
            continue
        grouped[(component, algo, _usage(record), ek, *_operation(record))].append(record)
    findings: list[dict[str, Any]] = []
    for identity, evidences in sorted(grouped.items()):
        component, algorithm, usage, evidence_kind, location, operation_anchor = identity
        sources: list[str] = []
        confidence_by_source: dict[str, float] = {}
        contexts = [_context(item) for item in evidences]
        seen: set[str] = set()
        unique_evidence: list[dict[str, Any]] = []
        for item in evidences:
            source = item.get("source", "unknown")
            if source not in sources:
                sources.append(source)
            confidence_by_source[source] = max(confidence_by_source.get(source, 0.0), float(item.get("confidence", 0.0)))
            fingerprint = json.dumps(item, sort_keys=True, default=str)
            if fingerprint not in seen:
                seen.add(fingerprint)
                unique_evidence.append(item)
        operation_conflict = any(
            len(algorithms) > 1
            for algorithms in operation_categories[(location, operation_anchor)].values()
        )
        conflicting_operations = sorted(
            {str(ctx["operation_id"]) for ctx in contexts if ctx.get("operation_id")}
        ) if operation_conflict else []
        if operation_conflict and not conflicting_operations:
            conflicting_operations = [operation_anchor]
        preferred = next((item for item in evidences if item.get("source") in {"ast", "cert", "rule"}), evidences[0])
        category = preferred.get("category", "unknown")
        category = {"signature": "signature", "hashing": "hash", "key_establishment": "key_exchange",
                    "tls": "protocol", "encryption": "encryption", "key_derivation": "kdf"}.get(usage, category)
        context_conflicts = {}
        def single_value(field, default, contexts=contexts, context_conflicts=context_conflicts):
            values = sorted({json.dumps(ctx[field], sort_keys=True, default=str)
                             for ctx in contexts if ctx[field] not in (None, "")})
            values = [json.loads(value) for value in values]
            if field == "key_size" and any(type(value) is not int or value <= 0 for value in values):
                context_conflicts[field] = values
                return default
            if len(values) > 1:
                context_conflicts[field] = values
            return values[0] if len(values) == 1 else default
        library = single_value("library", "")
        protocol = single_value("protocol", "")
        key_size = single_value("key_size", None)
        logical_id = hashlib.sha256(json.dumps(["operation-v2", *identity]).encode()).hexdigest()[:16]
        findings.append({
            "logical_asset_id": logical_id, "component": component, "algorithm": algorithm,
            "category": category, "location": preferred.get("location", ""),
            "sources": sorted(sources), "confidence_by_source": confidence_by_source,
            "conflict": bool(conflicting_operations or context_conflicts), "conflicting_operations": conflicting_operations,
            "operation_anchor": operation_anchor, "correlation_version": "operation-v2",
            "context_conflicts": context_conflicts,
            "evidence_list": unique_evidence, "source_count": len(sources), "usage": usage,
            "evidence_kind": evidence_kind, "library": library, "protocol": protocol, "key_size": key_size,
        })
    return findings
