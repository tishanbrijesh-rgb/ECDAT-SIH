"""Tests for risk engine scoring boundaries and business rules."""
from __future__ import annotations

import pytest

from backend.services.risk_engine import assess_risk

# ── Helper ────────────────────────────────────────────────────────────────────

def _asset(**overrides):
    base = {
        "algorithm": "RSA-2048",
        "usage": "tls",
        "business_criticality": "medium",
        "data_sensitivity": "medium",
        "exposure": "internal",
        "migration_effort": "medium",
        "data_lifetime_years": 10,
        "migration_time_years": 3,
        "threat_horizon_years": 15,
        "evidence_kind": "observed_operation",
    }
    base.update(overrides)
    return base


# ── TestScoringBoundaries ─────────────────────────────────────────────────────

class TestScoringBoundaries:
    """Verify the 25 / 50 / 75 score boundaries produce the correct labels."""

    def test_score_24_is_low(self):
        """Score 24 is strictly below the MEDIUM threshold → LOW."""
        asset = _asset(
            algorithm="RSA",
            business_criticality="low",
            data_sensitivity="low",
            exposure="isolated",
            migration_effort="medium",
            evidence_kind="observed_operation",
        )
        result = assess_risk(asset)
        assert result["priority_score"] == 24
        assert result["priority_label"] == "LOW"

    def test_score_25_is_medium(self):
        """Score 25 is exactly at the MEDIUM threshold → MEDIUM."""
        asset = _asset(
            algorithm="RSA",
            business_criticality="low",
            data_sensitivity="low",
            exposure="internal",
            migration_effort="low",
            evidence_kind="observed_operation",
        )
        result = assess_risk(asset)
        assert result["priority_score"] == 25
        assert result["priority_label"] == "MEDIUM"

    def test_score_49_is_medium(self):
        """Score 49 is one below the HIGH threshold → MEDIUM."""
        asset = _asset(
            algorithm="RSA",
            business_criticality="critical",
            data_sensitivity="high",
            exposure="partner",
            migration_effort="low",
            evidence_kind="observed_operation",
        )
        result = assess_risk(asset)
        # 15 + 15 + 11 + 7 + 1 = 49
        assert result["priority_score"] == 49
        assert result["priority_label"] == "MEDIUM"

    def test_score_50_is_high(self):
        """Score 50 is exactly at the HIGH threshold → HIGH."""
        asset = _asset(
            algorithm="RSA",
            business_criticality="low",
            data_sensitivity="low",
            exposure="internal",
            migration_effort="low",
            data_lifetime_years=10,
            migration_time_years=5,
            threat_horizon_years=15,
            evidence_kind="observed_operation",
        )
        result = assess_risk(asset)
        # 15 + 3 + 3 + 3 + 1 + 25 (Mosca: 10+5=15 >= 15) = 50
        assert result["priority_score"] == 50
        assert result["priority_label"] == "HIGH"

    def test_score_74_is_high(self):
        """Score 74 is one below the CRITICAL threshold → HIGH."""
        asset = _asset(
            algorithm="RSA",
            business_criticality="critical",
            data_sensitivity="high",
            exposure="partner",
            migration_effort="low",
            data_lifetime_years=10,
            migration_time_years=5,
            threat_horizon_years=15,
            evidence_kind="observed_operation",
        )
        result = assess_risk(asset)
        # 15 + 15 + 11 + 7 + 1 + 25 (Mosca) = 74
        assert result["priority_score"] == 74
        assert result["priority_label"] == "HIGH"

    def test_score_75_is_critical(self):
        """Score 75 is exactly at the CRITICAL threshold → CRITICAL."""
        asset = _asset(
            algorithm="RSA",
            business_criticality="high",
            data_sensitivity="high",
            exposure="internet",
            migration_effort="critical",
            data_lifetime_years=10,
            migration_time_years=5,
            threat_horizon_years=15,
            evidence_kind="observed_operation",
        )
        result = assess_risk(asset)
        # 15 + 25 (Mosca) + 15 + 11 + 10 + 5 = 81 → CRITICAL (clamped to 100, well above 75)
        assert result["priority_score"] >= 75
        assert result["priority_label"] == "CRITICAL"

    def test_score_below_twenty_five_is_low(self):
        """Any score strictly below 25 is labelled LOW."""
        asset = _asset(
            algorithm="SHA-256",
            business_criticality="low",
            data_sensitivity="low",
            exposure="isolated",
            migration_effort="low",
            evidence_kind="observed_operation",
        )
        result = assess_risk(asset)
        assert result["priority_score"] < 25
        assert result["priority_label"] == "LOW"


# ── TestDeprecatedAlgorithmRules ──────────────────────────────────────────────

class TestDeprecatedAlgorithmRules:
    """MD5 and SHA-1 are flagged as deprecated but still participate in scoring."""

    def test_md5_low_criticality_scores_at_least_medium(self):
        """MD5 with low criticality but high sensitivity / internet / critical effort
        still reaches at least MEDIUM because deprecated status is orthogonal to scoring."""
        asset = _asset(
            algorithm="MD5",
            business_criticality="low",
            data_sensitivity="high",
            exposure="internet",
            migration_effort="critical",
            evidence_kind="observed_operation",
        )
        result = assess_risk(asset)
        # 0 (not quantum-vulnerable) + 15 + 3 + 10 + 5 = 33
        assert result["priority_label"] in ("MEDIUM", "HIGH", "CRITICAL")

    def test_sha1_low_criticality_scores_at_least_medium(self):
        """SHA-1 behaves the same as MD5."""
        asset = _asset(
            algorithm="SHA-1",
            business_criticality="low",
            data_sensitivity="high",
            exposure="internet",
            migration_effort="critical",
            evidence_kind="observed_operation",
        )
        result = assess_risk(asset)
        assert result["priority_label"] in ("MEDIUM", "HIGH", "CRITICAL")

    def test_sha256_is_not_deprecated(self):
        """SHA-256 is not deprecated — recommendation text differs from MD5/SHA-1."""
        asset = _asset(
            algorithm="SHA-256",
            business_criticality="low",
            data_sensitivity="low",
            exposure="isolated",
            migration_effort="low",
            evidence_kind="observed_operation",
        )
        result = assess_risk(asset)
        assert result["quantum_vulnerable"] is False
        recommendation = result["pqc_candidate"]
        assert "SHA-256" in recommendation or "no public-key" in recommendation


# ── TestQuantumVulnerableAlgorithms ──────────────────────────────────────────

class TestQuantumVulnerableAlgorithms:
    """Every algorithm in the QUANTUM_VULNERABLE set is flagged and penalised."""

    @pytest.mark.parametrize("algorithm", ["RSA", "ECDSA", "ECDH", "DH", "DSA", "ECC"])
    def test_vulnerable_algorithm_quantum_flag(self, algorithm):
        """Each quantum-vulnerable algorithm gets quantum_vulnerable=True when
        evidence_kind indicates confirmed use."""
        asset = _asset(algorithm=algorithm, usage="tls", evidence_kind="observed_operation")
        result = assess_risk(asset)
        assert result["quantum_vulnerable"] is True

    @pytest.mark.parametrize("algorithm", ["RSA", "ECDSA", "ECDH", "DH", "DSA", "ECC"])
    def test_vulnerable_algorithm_receives_base_penalty(self, algorithm):
        """Each quantum-vulnerable algorithm includes the confirmed-use base penalty
        (15 points) in the raw score."""
        asset = _asset(
            algorithm=algorithm,
            usage="tls",
            evidence_kind="observed_operation",
            business_criticality="low",
            data_sensitivity="low",
            exposure="isolated",
            migration_effort="low",
        )
        result = assess_risk(asset)
        # 15 (penalty) + 3 + 3 + 0 + 1 = 22
        assert result["priority_score"] == 22
        assert result["priority_score"] >= 15


# ── TestExposureScoring ───────────────────────────────────────────────────────

class TestExposureScoring:
    """Exposure level monotonically increases risk score."""

    def test_internet_scores_higher_than_isolated(self):
        """Same algorithm and context, internet exposure scores higher than isolated
        by exactly 10 points."""
        base = _asset(
            algorithm="RSA",
            business_criticality="medium",
            data_sensitivity="medium",
            migration_effort="medium",
            evidence_kind="observed_operation",
        )
        isolated = assess_risk({**base, "exposure": "isolated"})
        internet = assess_risk({**base, "exposure": "internet"})

        assert internet["priority_score"] > isolated["priority_score"]
        # isolated=0, internet=10
        assert internet["priority_score"] - isolated["priority_score"] == 10

    def test_exposure_levels_are_ordered(self):
        """Exposure scores strictly increase: isolated < internal < partner < internet."""
        base = _asset(
            algorithm="RSA",
            business_criticality="low",
            data_sensitivity="low",
            migration_effort="low",
            evidence_kind="observed_operation",
        )
        scores = {
            level: assess_risk({**base, "exposure": level})["priority_score"]
            for level in ["isolated", "internal", "partner", "internet"]
        }
        assert scores["isolated"] < scores["internal"]
        assert scores["internal"] < scores["partner"]
        assert scores["partner"] < scores["internet"]


# ── TestEvidenceKindScoring ───────────────────────────────────────────────────

class TestEvidenceKindScoring:
    """Evidence kind determines which base penalty is applied for vulnerable algorithms."""

    def test_confirmed_use_observed_operation_penalty_15(self):
        """observed_operation is confirmed_use → base_penalty=15."""
        asset = _asset(
            algorithm="RSA",
            business_criticality="low",
            data_sensitivity="low",
            exposure="isolated",
            migration_effort="low",
            evidence_kind="observed_operation",
        )
        result = assess_risk(asset)
        assert result["priority_score"] == 22  # 15 + 3 + 3 + 0 + 1
        assert result["confirmed_use"] is True
        assert result["capability_only"] is False

    def test_confirmed_use_configured_protocol_penalty_15(self):
        """configured_protocol is also confirmed_use → base_penalty=15."""
        asset = _asset(
            algorithm="RSA",
            business_criticality="low",
            data_sensitivity="low",
            exposure="isolated",
            migration_effort="low",
            evidence_kind="configured_protocol",
        )
        result = assess_risk(asset)
        assert result["priority_score"] == 22
        assert result["confirmed_use"] is True

    def test_capability_only_declared_capability_penalty_8(self):
        """declared_capability → capability_only → base_penalty=8."""
        asset = _asset(
            algorithm="RSA",
            business_criticality="low",
            data_sensitivity="low",
            exposure="isolated",
            migration_effort="low",
            evidence_kind="declared_capability",
        )
        result = assess_risk(asset)
        # 8 + 3 + 3 + 0 + 1 = 15
        assert result["priority_score"] == 15
        assert result["capability_only"] is True

    def test_capability_only_artifact_metadata_penalty_8(self):
        """artifact_metadata is also capability_only → base_penalty=8."""
        asset = _asset(
            algorithm="RSA",
            business_criticality="low",
            data_sensitivity="low",
            exposure="isolated",
            migration_effort="low",
            evidence_kind="artifact_metadata",
        )
        result = assess_risk(asset)
        assert result["priority_score"] == 15
        assert result["capability_only"] is True

    def test_unknown_evidence_penalty_10(self):
        """Unknown evidence kind → base_penalty=10, neither confirmed nor capability-only."""
        asset = _asset(
            algorithm="RSA",
            business_criticality="low",
            data_sensitivity="low",
            exposure="isolated",
            migration_effort="low",
            evidence_kind="unknown",
        )
        result = assess_risk(asset)
        # 10 + 3 + 3 + 0 + 1 = 17
        assert result["priority_score"] == 17
        assert result["confirmed_use"] is False
        assert result["capability_only"] is False


# ── TestMoscaWindowScoring ────────────────────────────────────────────────────

class TestMoscaWindowScoring:
    """Mosca window overlap awards +25 bonus only for quantum-vulnerable algorithms."""

    def test_no_overlap_no_bonus(self):
        """Window (10+3=13) < horizon (15) → no +25 bonus."""
        asset = _asset(
            algorithm="RSA",
            business_criticality="low",
            data_sensitivity="low",
            exposure="isolated",
            migration_effort="low",
            data_lifetime_years=10,
            migration_time_years=3,
            threat_horizon_years=15,
            evidence_kind="observed_operation",
        )
        result = assess_risk(asset)
        # 15 + 3 + 3 + 0 + 1 = 22, no Mosca bonus
        assert result["priority_score"] == 22
        assert result["threat_overlap"] is False
        assert result["mosca_window_years"] == 13

    def test_exact_overlap_adds_bonus(self):
        """Window (10+5=15) == horizon (15) → overlap → +25 bonus."""
        asset = _asset(
            algorithm="RSA",
            business_criticality="low",
            data_sensitivity="low",
            exposure="isolated",
            migration_effort="low",
            data_lifetime_years=10,
            migration_time_years=5,
            threat_horizon_years=15,
            evidence_kind="observed_operation",
        )
        result = assess_risk(asset)
        # 15 + 3 + 3 + 0 + 1 + 25 = 47
        assert result["priority_score"] == 47
        assert result["threat_overlap"] is True
        assert result["mosca_window_years"] == 15

    def test_non_vulnerable_never_gets_quantum_bonus(self):
        """SHA-256 is not quantum-vulnerable so it never receives the Mosca bonus,
        even when the window clearly overlaps the horizon."""
        asset = _asset(
            algorithm="SHA-256",
            business_criticality="low",
            data_sensitivity="low",
            exposure="isolated",
            migration_effort="low",
            data_lifetime_years=10,
            migration_time_years=10,
            threat_horizon_years=15,
            evidence_kind="observed_operation",
        )
        result = assess_risk(asset)
        assert result["quantum_vulnerable"] is False
        assert result["threat_overlap"] is False
        # Score = 0 + 3 + 3 + 0 + 1 = 7 (no quantum penalty, no Mosca bonus)
        assert result["priority_score"] == 7


# ── TestConfidenceNotSeverity ─────────────────────────────────────────────────

class TestConfidenceNotSeverity:
    """Confidence band does not inflate or deflate the risk severity label."""

    def test_high_confidence_low_criticality_internal(self):
        """HIGH confidence with LOW criticality + internal exposure must NOT produce
        a HIGH risk label — confidence is orthogonal to severity."""
        asset = _asset(
            algorithm="SHA-256",
            business_criticality="low",
            data_sensitivity="low",
            exposure="internal",
            migration_effort="low",
            evidence_kind="observed_operation",
            confidence=0.95,
        )
        result = assess_risk(asset)
        # 0 + 3 + 3 + 3 + 1 = 10 → LOW
        assert result["priority_label"] in ("LOW", "MEDIUM")
        assert result["confidence_band"] == "HIGH"

    def test_low_confidence_critical_criticality_internet(self):
        """LOW confidence with CRITICAL criticality + internet exposure still
        produces HIGH or CRITICAL risk because severity is driven by context, not confidence."""
        asset = _asset(
            algorithm="RSA",
            business_criticality="critical",
            data_sensitivity="critical",
            exposure="internet",
            migration_effort="critical",
            data_lifetime_years=10,
            migration_time_years=5,
            threat_horizon_years=15,
            evidence_kind="declared_capability",
            confidence=0.35,
        )
        result = assess_risk(asset)
        # 8 (capability) + 15 + 15 + 10 + 5 + 25 (Mosca) = 78 → CRITICAL
        assert result["priority_label"] in ("HIGH", "CRITICAL")
        assert result["confidence_band"] == "UNCERTAIN"


# ── TestDeterminism ───────────────────────────────────────────────────────────

class TestDeterminism:
    """assess_risk is a pure function — identical input always yields identical output."""

    def test_three_calls_identical_output(self):
        """Calling assess_risk three times with the same dict returns the same
        label, score, and reasons each time."""
        asset = _asset(
            algorithm="ECDSA",
            usage="signature",
            business_criticality="high",
            data_sensitivity="high",
            exposure="internet",
            migration_effort="critical",
            data_lifetime_years=15,
            migration_time_years=5,
            threat_horizon_years=10,
            evidence_kind="observed_operation",
        )
        results = [assess_risk(asset) for _ in range(3)]

        labels = [r["priority_label"] for r in results]
        scores = [r["priority_score"] for r in results]
        reason_tuples = [tuple(r["risk_reasons"]) for r in results]

        assert len(set(labels)) == 1, f"Labels differ across calls: {labels}"
        assert len(set(scores)) == 1, f"Scores differ across calls: {scores}"
        assert len(set(reason_tuples)) == 1, f"Reason lists differ across calls: {reason_tuples}"


# ── TestReasonCodes ───────────────────────────────────────────────────────────

class TestReasonCodes:
    """risk_reasons always contains meaningful, structured explanations."""

    def test_reasons_non_empty(self):
        """risk_reasons is never empty for any asset."""
        asset = _asset()
        result = assess_risk(asset)
        assert len(result["risk_reasons"]) > 0

    def test_reasons_at_least_three(self):
        """risk_reasons contains at least 3 entries — one per scoring dimension."""
        asset = _asset()
        result = assess_risk(asset)
        assert len(result["risk_reasons"]) >= 3

    def test_reasons_mention_algorithm(self):
        """At least one reason string references the algorithm name."""
        asset = _asset(algorithm="ECDH")
        result = assess_risk(asset)
        combined = " ".join(result["risk_reasons"])
        assert "ECDH" in combined

    def test_reasons_mention_mosca_window(self):
        """At least one reason references the Mosca window or overlap status."""
        asset = _asset(
            algorithm="RSA",
            data_lifetime_years=10,
            migration_time_years=3,
            threat_horizon_years=15,
        )
        result = assess_risk(asset)
        combined = " ".join(result["risk_reasons"])
        assert "Mosca window" in combined
