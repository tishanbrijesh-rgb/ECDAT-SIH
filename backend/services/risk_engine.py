"""Transparent Mosca-style quantum and business risk assessment."""
from __future__ import annotations

QUANTUM_VULNERABLE = {"RSA", "ECDSA", "ECDH", "DH", "DSA", "ECC"}
LEVEL = {"low": 1, "medium": 2, "high": 3, "critical": 4}
EXPOSURE = {"isolated": 0, "internal": 1, "partner": 2, "internet": 3}

def _recommendation(algorithm: str, usage: str, migration_effort: str) -> tuple[str, bool]:
    usage = usage.lower()
    hybrid = migration_effort.lower() in {"high", "critical"}
    if algorithm in {"RSA", "ECDH", "DH", "ECC"} and usage in {"encryption", "key_establishment", "tls", "unknown"}:
        text = "Evaluate ML-KEM for key establishment"
    elif algorithm in {"RSA", "ECDSA", "DSA", "ECC"} and usage == "signature":
        text = "Evaluate ML-DSA; consider SLH-DSA where conservative hash-based signatures fit"
    elif algorithm == "AES":
        return "Retain symmetric design; prefer AES-256 for long-lived data", False
    elif algorithm.startswith("SHA") or algorithm in {"BLAKE2", "hash"}:
        return "Use SHA-256/SHA-3 with adequate output length; no public-key migration required", False
    elif algorithm in {"MD5", "SHA-1"}:
        return "Replace deprecated hash with SHA-256 or SHA-3 independent of quantum migration", False
    elif algorithm in {"ML-KEM", "ML-DSA", "SLH-DSA"}:
        return "Already aligned with a NIST post-quantum standard; validate implementation and protocol", False
    else:
        return "Assess algorithm, protocol role, compatibility and standards profile", False
    if hybrid:
        text += "; use a standards-approved classical/PQC hybrid transition where compatibility requires it"
    return text, hybrid

def assess_risk(asset: dict) -> dict:
    """Return a 0-100 explainable risk score and use-case-aware recommendation."""
    algorithm = str(asset.get("algorithm", ""))
    vulnerable = algorithm in QUANTUM_VULNERABLE
    criticality = str(asset.get("business_criticality") or "medium").lower()
    sensitivity = str(asset.get("data_sensitivity") or "medium").lower()
    exposure = str(asset.get("exposure") or "internal").lower()
    effort = str(asset.get("migration_effort") or "medium").lower()
    lifetime = max(0, int(asset.get("data_lifetime_years") or 0))
    migration = max(0, int(asset.get("migration_time_years") or 0))
    horizon = max(1, int(asset.get("threat_horizon_years") or 15))
    mosca_window = lifetime + migration
    overlap = vulnerable and mosca_window >= horizon
    score = 0
    reasons: list[str] = []
    if vulnerable:
        score += 35; reasons.append(f"{algorithm} is vulnerable to large-scale quantum attacks")
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
    return {
        "quantum_vulnerable": vulnerable, "priority_score": score, "priority_label": label,
        "pqc_candidate": recommendation, "hybrid_recommended": hybrid, "risk_reasons": reasons,
        "mosca_window_years": mosca_window, "threat_overlap": overlap,
    }
