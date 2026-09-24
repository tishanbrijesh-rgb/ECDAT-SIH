"""Regression tests for operation-v3 correlation anchors."""

from copy import deepcopy

from backend.services.correlator_v3 import _span_anchor


def test_span_anchor_uses_one_based_three_line_buckets():
    def finding(line):
        return {
            "location": "src/example.py",
            "evidence_list": [{"span": {"line_start": line, "column_start": 2}}],
        }

    assert _span_anchor(finding(1)) == _span_anchor(finding(3))
    assert _span_anchor(finding(3)) != _span_anchor(finding(4))


def test_public_v3_entrypoints_use_one_implementation():
    from backend.services.correlator import correlate, correlate_v3

    evidence = {
        "ast": [
            {
                "algorithm": "RSA",
                "category": "encryption",
                "source": "ast",
                "location": "src/crypto.py",
                "confidence": 0.9,
                "span": {"line_start": 10, "column_start": 4},
                "evidence": {
                    "usage": "encryption",
                    "evidence_kind": "observed_operation",
                    "operation_name": "encrypt",
                },
            }
        ]
    }

    assert correlate(evidence, mode="v3") == correlate_v3(evidence)


def test_v3_correlation_does_not_mutate_evidence_records():
    from backend.services.correlator_v3 import correlate

    evidence = {
        "ast": [
            {
                "algorithm": "RSA",
                "source": "ast",
                "location": "src/crypto.py",
                "span": {"line_start": 8},
                "evidence": {"evidence_kind": "observed_operation"},
            }
        ]
    }
    original = deepcopy(evidence)

    correlate(evidence)

    assert evidence == original


def test_v3_reports_cross_collector_ambiguity_for_distant_operations():
    from backend.services.correlator_v3 import correlate

    base = {
        "algorithm": "RSA",
        "location": "src/crypto.py",
        "confidence": 0.9,
        "category": "encryption",
    }
    evidence = {
        "mixed": [
            {
                **base,
                "source": "ast",
                "span": {"line_start": 10},
                "evidence": {"evidence_kind": "observed_operation"},
            },
            {
                **base,
                "source": "rule",
                "span": {"line_start": 80},
                "evidence": {"evidence_kind": "configured_protocol"},
            },
        ]
    }

    findings = correlate(evidence)

    assert len(findings) == 2
    assert all(len(finding["ambiguous_matches"]) == 1 for finding in findings)
    assert all(finding["confidence"] == 0.8 for finding in findings)


def test_v3_golden_cross_kind_links_and_moved_line_annotation():
    from backend.services.correlator_v3 import correlate

    base = {
        "algorithm": "ECDSA",
        "location": "services/signing.py",
        "span": {"line_start": 17, "column_start": 6},
        "confidence": 0.85,
        "category": "signature",
    }
    findings = correlate({
        "mixed": [
            {**base, "source": "ast", "evidence": {
                "usage": "sign", "evidence_kind": "observed_operation",
                "operation_name": "sign_payload",
            }},
            {**base, "source": "rule", "evidence": {
                "usage": "sign", "evidence_kind": "configured_protocol",
                "operation_name": "sign_payload",
            }},
        ]
    })

    assert [finding["evidence_kind"] for finding in findings] == [
        "configured_protocol", "observed_operation"
    ]
    assert findings[0]["cross_kind_links"] == ["observed_operation"]
    assert findings[1]["cross_kind_links"] == ["configured_protocol"]
    assert all(
        finding["span"]["moved_line_note"] == "[line=17;algo=ECDSA;col=6;ctx=op:sign_payload]"
        for finding in findings
    )
