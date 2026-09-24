"""Confidence scoring service.

Combines multiple evidence sources into a single confidence score, with
booster for agreeing sources and penalty for conflicting sources.

Phase 2: scoring is keyed by evidence_kind rather than source name,
so observed_operation and declared_capability are weighted independently
of which collector produced them.
"""
from __future__ import annotations

EVIDENCE_KIND_STRENGTH: dict[str, float] = {
    "observed_operation": 0.90,
    "configured_protocol": 0.85,
    "declared_capability": 0.65,
    "artifact_metadata": 0.50,
    "unknown": 0.30,
}


def score_finding(finding: dict) -> dict:
    """
    Compute confidence for a single, already-correlated finding.

    Phase 2: uses evidence_kind from the finding's evidence_list entries
    rather than the legacy source name. Falls back to SOURCE_STRENGTH
    (keyed by source) when evidence_kind is absent for backward compat.
    """
    # Collect evidence kinds from the evidence list; fall back to sources.
    evidence_list = finding.get("evidence_list") or []
    if evidence_list:
        kinds = []
        for item in evidence_list:
            ctx = item.get("evidence") or {}
            ek = ctx.get("evidence_kind") or item.get("evidence_kind") or ""
            if ek and ek not in kinds:
                kinds.append(ek)
    else:
        sources = finding.get("sources") or finding.get("source") or []
        if isinstance(sources, str):
            sources = [sources]
        kinds = list(dict.fromkeys(sources))

    if not kinds:
        reasons = ["no evidence"]
        return {"confidence": 0.0, "reasons": reasons}

    # Map evidence kinds (or legacy source names) to strength values.
    strengths = [EVIDENCE_KIND_STRENGTH.get(ek, EVIDENCE_KIND_STRENGTH.get("unknown")) for ek in kinds]
    avg = sum(strengths) / len(strengths)

    # +0.08 per distinct agreeing evidence kind beyond the first
    bonus = min(0.20, 0.08 * max(0, len(kinds) - 1))
    score = avg + bonus

    # Conflict penalty
    if finding.get("conflict"):
        score -= 0.20

    # Clamp
    score = max(0.0, min(1.0, round(score, 4)))

    reasons = [f"{len(kinds)} evidence kind(s)", f"avg={avg:.2f}", f"+bonus={bonus:.2f}"]
    if finding.get("conflict"):
        reasons.append("-0.20 operation conflict")
    return {"confidence": score, "reasons": reasons}
