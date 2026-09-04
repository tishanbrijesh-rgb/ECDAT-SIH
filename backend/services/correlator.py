"""Logical evidence graph builder for ECDAT discovery assurance."""
from __future__ import annotations
import hashlib
import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any

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
    return {
        "usage": details.get("usage") or "unknown",
        "library": details.get("library") or details.get("package") or details.get("groupId") or "",
        "protocol": details.get("protocol") or "",
        "key_size": details.get("key_size"),
        "operation_id": details.get("operation_id"),
    }

def correlate(evidence_dict: dict) -> list[dict[str, Any]]:
    """Correlate scanner records into logical component/algorithm findings."""
    records = [record for evidences in evidence_dict.values() for record in evidences]
    operation_categories: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for record in records:
        operation = _context(record).get("operation_id")
        if operation:
            operation_categories[str(operation)][record.get("category", "unknown")].add(record.get("algorithm", "unknown"))
    component_strong_algorithms: dict[str, set[str]] = defaultdict(set)
    for record in records:
        if record.get("source") != "dep":
            component_strong_algorithms[_component(record.get("location", ""))].add(record.get("algorithm", "unknown"))
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        component = _component(record.get("location", ""))
        if record.get("source") == "dep" and component_strong_algorithms[component] and record.get("algorithm") not in component_strong_algorithms[component]:
            continue
        grouped[(component, record.get("algorithm", "unknown"))].append(record)
    findings: list[dict[str, Any]] = []
    for (component, algorithm), evidences in grouped.items():
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
        conflicting_operations = sorted({str(ctx["operation_id"]) for ctx in contexts if ctx.get("operation_id") and any(len(algorithms) > 1 for algorithms in operation_categories[str(ctx["operation_id"])].values())})
        preferred = next((item for item in evidences if item.get("source") in {"ast", "cert", "rule"}), evidences[0])
        usage = next((ctx["usage"] for ctx in contexts if ctx["usage"] != "unknown"), "unknown")
        category = preferred.get("category", "unknown")
        if category == "signature":
            usage = "signature"
        elif category == "hash":
            usage = "hashing"
        elif category == "key_exchange":
            usage = "key_establishment"
        elif category == "protocol":
            usage = "tls"
        library = next((ctx["library"] for ctx in contexts if ctx["library"]), "")
        protocol = next((ctx["protocol"] for ctx in contexts if ctx["protocol"]), "")
        key_size = next((ctx["key_size"] for ctx in contexts if ctx["key_size"]), None)
        logical_id = hashlib.sha256(f"{component}:{algorithm}:{usage}".encode()).hexdigest()[:16]
        findings.append({
            "logical_asset_id": logical_id, "component": component, "algorithm": algorithm,
            "category": category, "location": preferred.get("location", ""),
            "sources": sorted(sources), "confidence_by_source": confidence_by_source,
            "conflict": bool(conflicting_operations), "conflicting_operations": conflicting_operations,
            "evidence_list": unique_evidence, "source_count": len(sources), "usage": usage,
            "library": library, "protocol": protocol, "key_size": key_size,
        })
    return sorted(findings, key=lambda finding: (finding["component"], finding["algorithm"]))
