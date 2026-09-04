"""Confidence scoring service.

Combines multiple evidence sources into a single confidence score, with
booster for agreeing sources and penalty for conflicting sources.
"""

from __future__ import annotations

SOURCE_STRENGTH: dict[str, float] = {
    "ast": 0.90,
    "cert": 0.95,
    "dep": 0.70,
    "semgrep": 0.85,
    "rule": 0.82,
    "binary": 0.55,
}


def score_finding(finding: dict) -> dict:
    """
    Compute confidence for a single, already-correlated finding.

    Input shape:
        {
          "algorithm": "RSA",
          "sources": ["ast", "dep"],
          "confidence_by_source": {"ast": 0.9, "dep": 0.7},
          "conflict": False
        }

    Returns:
        dict with keys: confidence (0..1), reasons (list[str])
    """
    sources: list[str] = finding.get("sources") or finding.get("source") or []
    # Normalise to list whether input is list or string
    if isinstance(sources, str):
        sources = [sources]
    # Repeated evidence from one collector is not independent agreement.
    sources = list(dict.fromkeys(sources))
    conf_by_source: dict[str, float] = finding.get("confidence_by_source", {})

    if not sources:
        reasons = ["no sources"]
        return {"confidence": 0.0, "reasons": reasons}

    # If the caller didn't supply confidence_by_source, fall back to SOURCE_STRENGTH
    if not conf_by_source:
        conf_by_source = {s: SOURCE_STRENGTH.get(s, 0.5) for s in sources}

    # Average strength
    strengths = [conf_by_source.get(s, SOURCE_STRENGTH.get(s, 0.5)) for s in sources]
    avg = sum(strengths) / len(strengths)

    # +0.08 per distinct agreeing source beyond the first
    bonus = min(0.20, 0.08 * max(0, len(sources) - 1))
    score = avg + bonus

    # Conflict penalty
    if finding.get("conflict"):
        score -= 0.20

    # Clamp
    score = max(0.0, min(1.0, round(score, 4)))

    reasons = [f"{len(sources)} source(s)", f"avg={avg:.2f}", f"+bonus={bonus:.2f}"]
    if finding.get("conflict"):
        reasons.append("-0.20 operation conflict")
    return {"confidence": score, "reasons": reasons}
