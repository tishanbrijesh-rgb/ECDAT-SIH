"""Transparent Mosca-style quantum and business risk assessment."""
from __future__ import annotations

import re

from backend.services.calibration import classify_confidence

QUANTUM_VULNERABLE = {"RSA", "ECDSA", "ECDH", "DH", "DSA", "ECC"}
LEVEL = {"low": 1, "medium": 2, "high": 3, "critical": 4}
EXPOSURE = {"isolated": 0, "internal": 1, "partner": 2, "internet": 3}

# Suffixes stripped from algorithm strings before lookup.
# Handles RSA-2048, ECDSA-P256, DH-1024, AES-256, SHA-256, etc.
_ALGO_SUFFIX_RE = re.compile(r"[-_]\d+.*$")


def _base_algo(raw: str) -> str:
    """Strip key-size and curve suffixes: RSA-2048 -> RSA, ECDSA-P256 -> ECDSA."""
    return _ALGO_SUFFIX_RE.sub("", raw).strip()


def _vulnerable_algorithms() -> set[str]:
    """Return both base names and common suffixed variants for quantum-vulnerable algos."""
    result = set(QUANTUM_VULNERABLE)
    for base in QUANTUM_VULNERABLE:
        result.add(f"{base}-2048")
        result.add(f"{base}-4096")
    return result


_VULNERABLE_LOOKUP = _vulnerable_algorithms()

def _provenance_label(asset: dict, field: str, default) -> str:
    """Label a field as user-provided or policy-default.

    Uses ``in`` so that a caller-supplied value of ``None`` or empty string still
    counts as user-provided (the caller explicitly cleared it).
    """
    return "user-provided" if field in asset else "policy-default"


# Fields whose provenance is tracked in every ``assess_risk`` response.
_RISK_CONTEXT_FIELDS: list[str] = [
    "business_criticality",
    "data_sensitivity",
    "data_lifetime_years",
    "migration_time_years",
    "threat_horizon_years",
    "exposure",
    "migration_effort",
]

# Policy defaults used by the scanner runner when a field is absent.
_DEFAULTS: dict[str, object] = {
    "business_criticality": "medium",
    "data_sensitivity": "medium",
    "data_lifetime_years": 10,
    "migration_time_years": 3,
    "threat_horizon_years": 15,
    "exposure": "internal",
    "migration_effort": "medium",
}

def _recommendation(algorithm: str, usage: str, migration_effort: str) -> tuple[str, bool]:
    usage = usage.lower()
    hybrid = migration_effort.lower() in {"high", "critical"}
    if algorithm in {"RSA", "ECDH", "DH", "ECC"} and usage in {"encryption", "key_establishment", "tls"}:
        text = "Evaluate ML-KEM for key establishment"
    elif algorithm in {"RSA", "ECDSA", "DSA", "ECC"} and usage == "signature":
        text = "Evaluate ML-DSA; consider SLH-DSA where conservative hash-based signatures fit"
    elif algorithm == "AES":
        return "Retain symmetric design; prefer AES-256 for long-lived data", False
    elif algorithm in {"MD5", "SHA-1"}:
        return "Replace deprecated hash with SHA-256 or SHA-3 independent of quantum migration", False
    elif algorithm.startswith("SHA") or algorithm in {"BLAKE2", "hash"}:
        return "Use SHA-256/SHA-3 with adequate output length; no public-key migration required", False
    elif algorithm in {"ML-KEM", "ML-DSA", "SLH-DSA"}:
        return "Already aligned with a NIST post-quantum standard; validate implementation and protocol", False
    else:
        return "Assess algorithm, protocol role, compatibility and standards profile", False
    if hybrid:
        text += "; use a standards-approved classical/PQC hybrid transition where compatibility requires it"
    return text, hybrid

def assess_risk(asset: dict, user_provided_fields: set[str] | None = None) -> dict:
    """Return a 0-100 explainable risk score and use-case-aware recommendation.

    Phase 2: distinguishes confirmed_use (observed_operation / configured_protocol)
    from capability_only (declared_capability / artifact_metadata). Capability-only
    exposures receive a lower base score because actual usage is not confirmed.

    Each risk-context input carries a provenance label: "user-provided" when the
    caller supplied the value explicitly, "policy-default" when the engine fell
    back to the built-in default.

    The caller may pass ``user_provided_fields`` — a set of field names that were
    present in the original asset dict before defaults were filled in (used by the
    scanner runner). When absent, ``_provenance_label`` checks the asset dict
    directly, which also works for POST/PATCH requests where defaults haven't
    been applied.
    """
    algorithm = str(asset.get("algorithm", ""))
    base_algo = _base_algo(algorithm)
    vulnerable = base_algo in QUANTUM_VULNERABLE
    criticality = str(asset.get("business_criticality") or "medium").lower()
    sensitivity = str(asset.get("data_sensitivity") or "medium").lower()
    exposure = str(asset.get("exposure") or "internal").lower()
    effort = str(asset.get("migration_effort") or "medium").lower()
    lifetime = max(0, int(asset.get("data_lifetime_years") or 0))
    migration = max(0, int(asset.get("migration_time_years") or 0))
    horizon = max(1, int(asset.get("threat_horizon_years") or 15))
    mosca_window = lifetime + migration
    overlap = vulnerable and mosca_window >= horizon

    # Provenance for each risk-context input.
    provenance: dict[str, str] = {}
    for field in _RISK_CONTEXT_FIELDS:
        if user_provided_fields is not None:
            provenance[field] = "user-provided" if field in user_provided_fields else "policy-default"
        else:
            provenance[field] = _provenance_label(asset, field, _DEFAULTS.get(field))

    # Phase 2 evidence-kind-aware base adjustment
    evidence_kind = str(asset.get("evidence_kind") or asset.get("evidence_quality") or "unknown").lower()
    confirmed_use = evidence_kind in {"observed_operation", "configured_protocol"}
    capability_only = evidence_kind in {"declared_capability", "artifact_metadata"}
    base_penalty = 15 if confirmed_use else (8 if capability_only else 10)

    score = 0
    reasons: list[str] = []
    if vulnerable:
        score += base_penalty
        note = "confirmed use of" if confirmed_use else ("capability-only exposure to" if capability_only else "evidence of")
        reasons.append(f"{algorithm} ({note}) is vulnerable to large-scale quantum attacks")
    else:
        reasons.append(f"{algorithm or 'Algorithm'} has no modeled Shor-algorithm exposure")
    if overlap:
        score += 25; reasons.append(f"Mosca window {mosca_window}y overlaps {horizon}y threat horizon")
    else:
        reasons.append(f"Mosca window {mosca_window}y does not overlap {horizon}y threat horizon")
    score += {1: 3, 2: 7, 3: 11, 4: 15}[LEVEL.get(sensitivity, 2)]
    score += {1: 3, 2: 7, 3: 11, 4: 15}[LEVEL.get(criticality, 2)]
    score += {0: 0, 1: 3, 2: 7, 3: 10}[EXPOSURE.get(exposure, 1)]
    score += {1: 1, 2: 3, 3: 5, 4: 5}[LEVEL.get(effort, 2)]
    reasons.extend([
        f"Data sensitivity is {sensitivity}",
        f"Business criticality is {criticality}",
        f"Exposure is {exposure}",
        f"Migration effort is {effort}",
    ])
    score = min(100, score)
    label = "CRITICAL" if score >= 75 else "HIGH" if score >= 50 else "MEDIUM" if score >= 25 else "LOW"
    recommendation, hybrid = _recommendation(algorithm, str(asset.get("usage") or "unknown"), effort)

    # Phase 5: classify the raw confidence score into a calibrated band.
    raw_confidence = float(asset.get("confidence", 0.0))
    confidence_classification = classify_confidence(raw_confidence)

    return {
        "quantum_vulnerable": vulnerable, "priority_score": score, "priority_label": label,
        "pqc_candidate": recommendation, "hybrid_recommended": hybrid, "risk_reasons": reasons,
        "mosca_window_years": mosca_window, "threat_overlap": overlap,
        "confirmed_use": confirmed_use, "capability_only": capability_only,
        "evidence_kind": evidence_kind,
        "confidence_band": confidence_classification["band"],
        "confidence_interpretation": f"{confidence_classification['label']} — {confidence_classification['description']}",
        "risk_context_provenance": provenance,
    }
