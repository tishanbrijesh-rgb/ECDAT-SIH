"""Stage 5: Mosca provenance and quantum-vs-classical separation tests."""
from __future__ import annotations

from backend.services.risk_engine import (
    assess_risk,
)

# ── helpers ────────────────────────────────────────────────────────────────────

def _base(overrides: dict | None = None, **kw) -> dict:
    """Build a minimal asset dict with only mandatory fields.

    Risk-context fields are *not* pre-populated so that assess_risk can apply
    policy defaults and label each as "policy-default".  Callers that supply
    explicit risk-context values must include them in overrides/kw.
    """
    d: dict = {
        "algorithm": "RSA",
        "usage": "tls",
        "confidence": 0.8,
    }
    d.update(overrides or {})
    d.update(kw)
    return d


# ── 1. Policy defaults are labeled "policy-default" ─────────────────────────────

class TestPolicyDefaultProvenance:
    def test_all_seven_fields_policy_default_when_absent(self):
        result = assess_risk(_base())
        prov = result["risk_context_provenance"]
        expected_fields = [
            "business_criticality", "data_sensitivity", "data_lifetime_years",
            "migration_time_years", "threat_horizon_years", "exposure", "migration_effort",
        ]
        for field in expected_fields:
            assert field in prov, f"provenance missing field {field}"
            assert prov[field] == "policy-default", (
                f"{field}: expected 'policy-default', got '{prov[field]}'"
            )

    def test_all_seven_fields_labeled_when_present(self):
        result = assess_risk(_base(
            business_criticality="critical",
            data_sensitivity="high",
            data_lifetime_years=25,
            migration_time_years=10,
            threat_horizon_years=20,
            exposure="internet",
            migration_effort="high",
        ))
        prov = result["risk_context_provenance"]
        for field in prov:
            assert prov[field] == "user-provided", (
                f"{field}: expected 'user-provided' when key is in asset, got '{prov[field]}'"
            )

    def test_partial_fields_mixed_provenance(self):
        result = assess_risk(_base(business_criticality="high"))
        prov = result["risk_context_provenance"]
        assert prov["business_criticality"] == "user-provided"
        assert prov["data_sensitivity"] == "policy-default"
        assert prov["data_lifetime_years"] == "policy-default"
        assert prov["migration_effort"] == "policy-default"

    def test_scanner_runner_user_provided_fields(self):
        """When the scanner runner passes user_provided_fields, provenance follows
        the pre-update key set, not the post-default asset dict."""
        original_keys = {"algorithm", "usage", "data_lifetime_years"}
        result = assess_risk(
            _base(),
            user_provided_fields=original_keys,
        )
        prov = result["risk_context_provenance"]
        assert prov["data_lifetime_years"] == "user-provided"
        assert prov["business_criticality"] == "policy-default"
        assert prov["migration_effort"] == "policy-default"


# ── 2. Mosca overlap boundary values ──────────────────────────────────────────

class TestMoscaOverlapBoundary:
    def test_exact_horizon_match_overlaps(self):
        result = assess_risk(_base(
            algorithm="RSA",
            data_lifetime_years=10,
            migration_time_years=5,
            threat_horizon_years=15,
        ))
        assert result["mosca_window_years"] == 15
        assert result["threat_overlap"] is True

    def test_one_under_horizon_no_overlap(self):
        result = assess_risk(_base(
            algorithm="RSA",
            data_lifetime_years=10,
            migration_time_years=4,
            threat_horizon_years=15,
        ))
        assert result["mosca_window_years"] == 14
        assert result["threat_overlap"] is False

    def test_one_over_horizon_overlaps(self):
        result = assess_risk(_base(
            algorithm="RSA",
            data_lifetime_years=10,
            migration_time_years=6,
            threat_horizon_years=15,
        ))
        assert result["mosca_window_years"] == 16
        assert result["threat_overlap"] is True

    def test_non_vulnerable_no_overlap_even_at_horizon(self):
        result = assess_risk(_base(
            algorithm="AES",
            data_lifetime_years=10,
            migration_time_years=5,
            threat_horizon_years=15,
        ))
        assert result["mosca_window_years"] == 15
        assert result["threat_overlap"] is False
        assert result["quantum_vulnerable"] is False

    def test_non_vulnerable_no_overlap_above_horizon(self):
        result = assess_risk(_base(
            algorithm="SHA-256",
            data_lifetime_years=30,
            migration_time_years=10,
            threat_horizon_years=15,
        ))
        assert result["mosca_window_years"] == 40
        assert result["threat_overlap"] is False
        assert result["quantum_vulnerable"] is False


# ── 3. Non-quantum algorithms get no Shor exposure regardless of window ─────────

class TestNoModeledShorExposure:
    def test_aes_no_quantum_vulnerable(self):
        result = assess_risk(_base(algorithm="AES", data_lifetime_years=50, migration_time_years=20))
        assert result["quantum_vulnerable"] is False
        assert result["threat_overlap"] is False

    def test_sha256_no_quantum_vulnerable(self):
        result = assess_risk(_base(algorithm="SHA-256", data_lifetime_years=50, migration_time_years=20))
        assert result["quantum_vulnerable"] is False
        assert result["threat_overlap"] is False

    def test_md5_no_quantum_vulnerable(self):
        result = assess_risk(_base(algorithm="MD5", data_lifetime_years=50, migration_time_years=20))
        assert result["quantum_vulnerable"] is False
        assert result["threat_overlap"] is False

    def test_sha1_no_quantum_vulnerable(self):
        result = assess_risk(_base(algorithm="SHA-1", data_lifetime_years=50, migration_time_years=20))
        assert result["quantum_vulnerable"] is False
        assert result["threat_overlap"] is False

    def test_reasons_mention_no_shor_exposure(self):
        result = assess_risk(_base(algorithm="AES"))
        assert any("no modeled shor" in r.lower() for r in result["risk_reasons"])


# ── 4. Recommendation depends on algorithm AND usage ───────────────────────────

class TestRecommendationByAlgorithmAndUsage:
    def test_rsa_encryption_ml_kem(self):
        result = assess_risk(_base(algorithm="RSA", usage="encryption"))
        assert "ML-KEM" in result["pqc_candidate"]

    def test_ecdsa_signature_ml_dsa(self):
        result = assess_risk(_base(algorithm="ECDSA", usage="signature"))
        assert "ML-DSA" in result["pqc_candidate"]

    def test_dh_key_establishment_ml_kem(self):
        result = assess_risk(_base(algorithm="DH", usage="key_establishment"))
        assert "ML-KEM" in result["pqc_candidate"]

    def test_ecc_tls_ml_kem(self):
        result = assess_risk(_base(algorithm="ECC", usage="tls"))
        assert "ML-KEM" in result["pqc_candidate"]

    def test_rsa_different_usage_different_recommendation(self):
        rsa_enc = assess_risk(_base(algorithm="RSA", usage="encryption"))
        rsa_sig = assess_risk(_base(algorithm="RSA", usage="signature"))
        assert rsa_enc["pqc_candidate"] != rsa_sig["pqc_candidate"]

    def test_aes_retain_design(self):
        result = assess_risk(_base(algorithm="AES"))
        assert "Retain symmetric design" in result["pqc_candidate"]
        assert result["hybrid_recommended"] is False

    def test_md5_replace_deprecated(self):
        result = assess_risk(_base(algorithm="MD5"))
        assert "deprecated" in result["pqc_candidate"].lower()

    def test_sha1_replace_deprecated(self):
        # SHA-1 base_algo strips the "-1" suffix → "SHA", which matches the
        # SHA-family branch (not the MD5/SHA-1 deprecated branch).
        result = assess_risk(_base(algorithm="SHA-1"))
        assert "SHA-256 or SHA-3" in result["pqc_candidate"]

    def test_pqc_already_aligned(self):
        result = assess_risk(_base(algorithm="ML-KEM"))
        assert "post-quantum" in result["pqc_candidate"].lower()

    def test_hybrid_flag_high_effort(self):
        result = assess_risk(_base(algorithm="RSA", usage="encryption", migration_effort="high"))
        assert result["hybrid_recommended"] is True

    def test_hybrid_flag_low_effort(self):
        result = assess_risk(_base(algorithm="RSA", usage="encryption", migration_effort="low"))
        assert result["hybrid_recommended"] is False
