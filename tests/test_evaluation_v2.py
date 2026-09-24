"""Tests for the v2 operation-level evaluator in backend.services.evaluation."""
import tempfile
import unittest
from pathlib import Path

from backend.services.evaluation import (
    EvaluatedOperation,
    _build_alias_map,
    _match_operations,
    _normalise_usage,
    _operation_match_score,
    _resolve_algorithm,
    evaluate_assets,
)


def _finding(**overrides):
    """Create a minimal correlated finding dict."""
    base = {
        "algorithm": "RSA",
        "category": "encryption",
        "source": ["rule"],
        "location": "test-repo/app/a.py",
        "confidence": 0.82,
        "evidence_json": {
            "component": "app",
            "usage": "encryption",
            "key_size": 2048,
            "operation_id": "op-1",
            "line": 10,
            "evidence_list": [],
        },
    }
    base.update(overrides)
    return base


def _ground_truth_v2(
    assets=None,
    alias_pairs=None,
    cert_expectations=None,
    blind_spots=None,
):
    """Build a minimal v2 ground_truth.json dict."""
    return {
        "description": "Test v2 ground truth",
        "evaluation_version": 2,
        "assets": assets or [{"component": "app", "algorithm": "AES"}],
        "alias_pairs": alias_pairs or [],
        "cert_expectations": cert_expectations or [],
        "blind_spots": blind_spots or [],
    }


class AliasResolutionTests(unittest.TestCase):
    """Tests for algorithm alias resolution."""

    def test_no_aliases_returns_identity(self):
        alias_map = _build_alias_map([])
        self.assertEqual(_resolve_algorithm("AES", alias_map), "AES")

    def test_single_pair_maps_both_directions(self):
        alias_map = _build_alias_map(
            [{"algorithms": ["RSA", "RSA-2048"], "same_family": True}]
        )
        self.assertEqual(_resolve_algorithm("RSA", alias_map), "RSA")
        self.assertEqual(_resolve_algorithm("RSA-2048", alias_map), "RSA")

    def test_multiple_pairs(self):
        alias_map = _build_alias_map(
            [
                {"algorithms": ["RSA", "RSA-2048"], "same_family": True},
                {"algorithms": ["AES", "AES-256-GCM"], "same_family": True},
                {"algorithms": ["ECDSA", "ECDSA-P256"], "same_family": True},
            ]
        )
        self.assertEqual(_resolve_algorithm("RSA-2048", alias_map), "RSA")
        self.assertEqual(_resolve_algorithm("AES-256-GCM", alias_map), "AES")
        self.assertEqual(_resolve_algorithm("ECDSA-P256", alias_map), "ECDSA")

    def test_pair_with_more_than_two_entries(self):
        alias_map = _build_alias_map(
            [
                {
                    "algorithms": ["SHA-256", "SHA2-256", "SHA256"],
                    "same_family": True,
                }
            ]
        )
        for variant in ("SHA-256", "SHA2-256", "SHA256"):
            self.assertEqual(_resolve_algorithm(variant, alias_map), "SHA-256")

    def test_pair_of_length_one_is_ignored(self):
        alias_map = _build_alias_map(
            [{"algorithms": ["AES"], "same_family": True}]
        )
        self.assertEqual(_resolve_algorithm("AES", alias_map), "AES")

    def test_unknown_algorithm_passthrough(self):
        alias_map = _build_alias_map(
            [{"algorithms": ["RSA", "RSA-2048"], "same_family": True}]
        )
        self.assertEqual(_resolve_algorithm("BOGUS", alias_map), "BOGUS")


class UsageNormalisationTests(unittest.TestCase):
    def test_known_aliases(self):
        self.assertEqual(_normalise_usage("sign"), "signature")
        self.assertEqual(_normalise_usage("verify"), "signature")
        self.assertEqual(_normalise_usage("hash"), "hashing")
        self.assertEqual(_normalise_usage("key_exchange"), "key_establishment")

    def test_canonical_unchanged(self):
        for usage in (
            "encryption",
            "hashing",
            "signature",
            "key_establishment",
            "tls",
            "unknown",
        ):
            self.assertEqual(_normalise_usage(usage), usage)


class HungarianAlgorithmTests(unittest.TestCase):
    def test_square_perfect_match(self):
        e = [
            EvaluatedOperation(
                "A", "A", "c1", usage="enc", key_size=256
            ),
            EvaluatedOperation(
                "B", "B", "c2", usage="sign", key_size=2048
            ),
        ]
        a = [
            EvaluatedOperation(
                "A", "A", "c1", usage="enc", key_size=256
            ),
            EvaluatedOperation(
                "B", "B", "c2", usage="sign", key_size=2048
            ),
        ]
        pairs, miss, unexp, _ = _match_operations(e, a)
        self.assertEqual(len(pairs), 2)
        self.assertEqual(miss, [])
        self.assertEqual(unexp, [])

    def test_rectangular_extra_actual(self):
        e = [EvaluatedOperation("A", "A", "c1", usage="enc")]
        a = [
            EvaluatedOperation("A", "A", "c1", usage="enc"),
            EvaluatedOperation("B", "B", "c1", usage="enc"),
        ]
        pairs, miss, unexp, _ = _match_operations(e, a)
        self.assertEqual(len(pairs), 1)
        self.assertEqual(miss, [])
        self.assertEqual(len(unexp), 1)

    def test_rectangular_extra_expected(self):
        e = [
            EvaluatedOperation("A", "A", "c1", usage="enc"),
            EvaluatedOperation("B", "B", "c1", usage="enc"),
        ]
        a = [EvaluatedOperation("A", "A", "c1", usage="enc")]
        pairs, miss, unexp, _ = _match_operations(e, a)
        self.assertEqual(len(pairs), 1)
        self.assertEqual(len(miss), 1)
        self.assertEqual(unexp, [])

    def test_empty_sides(self):
        e = [EvaluatedOperation("A", "A", "c1")]
        pairs, miss, unexp, _ = _match_operations(e, [])
        self.assertEqual(pairs, [])
        self.assertEqual(len(miss), 1)
        self.assertEqual(unexp, [])

        pairs, miss, unexp, _ = _match_operations([], [e[0]])
        self.assertEqual(pairs, [])
        self.assertEqual(miss, [])
        self.assertEqual(len(unexp), 1)

    def test_score_prefers_usage_match_over_key_size(self):
        """Usage match is worth more than key_size alone."""
        e = [EvaluatedOperation("A", "A", "c1", usage="enc", key_size=256)]
        a = [
            EvaluatedOperation(
                "A", "A", "c1", usage="enc", key_size=512
            ),
            EvaluatedOperation(
                "A", "A", "c1", usage="sign", key_size=256
            ),
        ]
        pairs, _miss, _unexp, scores = _match_operations(e, a)
        self.assertEqual(len(pairs), 1)
        self.assertEqual(scores["usage_correct"], 1)


class OperationMatchScoreTests(unittest.TestCase):
    def test_perfect_match_scores_highest(self):
        e = EvaluatedOperation(
            "A", "A", "c1", usage="enc", key_size=256
        )
        a = EvaluatedOperation(
            "A", "A", "c1", usage="enc", key_size=256
        )
        self.assertEqual(
            _operation_match_score(e, a), 101
        )  # 2*100 + 1

    def test_usage_match_only(self):
        e = EvaluatedOperation(
            "A", "A", "c1", usage="enc", key_size=256
        )
        a = EvaluatedOperation(
            "A", "A", "c1", usage="enc", key_size=512
        )
        self.assertEqual(
            _operation_match_score(e, a), 100
        )  # 1*100 + 1

    def test_key_size_match_only(self):
        e = EvaluatedOperation(
            "A", "A", "c1", usage="enc", key_size=256
        )
        a = EvaluatedOperation(
            "A", "A", "c1", usage="sign", key_size=256
        )
        self.assertEqual(
            _operation_match_score(e, a), 0
        )  # 0*100 + 0

    def test_no_match(self):
        e = EvaluatedOperation(
            "A", "A", "c1", usage="enc", key_size=256
        )
        a = EvaluatedOperation(
            "A", "A", "c1", usage="sign", key_size=512
        )
        self.assertEqual(
            _operation_match_score(e, a), -1
        )  # 0*100 - 1

    def test_none_key_size_equality(self):
        e = EvaluatedOperation(
            "A", "A", "c1", usage="enc", key_size=None
        )
        a = EvaluatedOperation(
            "A", "A", "c1", usage="enc", key_size=None
        )
        # None == None is True in Python
        self.assertTrue(
            _operation_match_score(e, a) >= 100
        )


class V2EvaluateAssetsTests(unittest.TestCase):
    """End-to-end tests for the v2 evaluator."""

    def _scan_fixture(self, findings):
        """Helper: create temp dir with ground_truth.json and run evaluate."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            truth = _ground_truth_v2()
            (root / "ground_truth.json").write_text(
                __import__("json").dumps(truth), encoding="utf-8"
            )
            return evaluate_assets(findings, str(root))

    def test_perfect_match_returns_100(self):
        result = self._scan_fixture([_finding()])
        self.assertTrue(result["available"])
        self.assertEqual(result["true_positives"], 1)
        self.assertEqual(result["false_positives"], 0)
        self.assertEqual(result["false_negatives"], 0)
        self.assertEqual(result["precision"], 1.0)
        self.assertEqual(result["recall"], 1.0)
        self.assertEqual(result["f1"], 1.0)

    def test_missing_asset_is_false_negative(self):
        result = self._scan_fixture([])
        self.assertEqual(result["false_negatives"], 1)
        self.assertEqual(result["recall"], 0.0)

    def test_extra_asset_is_false_positive(self):
        result = self._scan_fixture(
            [
                _finding(),
                _finding(
                    algorithm="MD5",
                    evidence_json={
                        "component": "app",
                        "usage": "hashing",
                        "key_size": None,
                        "operation_id": "op-2",
                        "evidence_list": [],
                    },
                ),
            ]
        )
        self.assertEqual(result["false_positives"], 1)
        self.assertEqual(result["precision"], 0.5)

    def test_v2_reports_operation_granularity(self):
        result = self._scan_fixture([_finding()])
        self.assertEqual(result["granularity"], "operation")
        self.assertEqual(result["evaluation_version"], 2)

    def test_v1_ground_truth_still_works(self):
        """A v1 ground truth (no evaluation_version) must fall back to v1 logic."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            truth = {
                "assets": [
                    {"component": "app", "algorithm": "RSA"}
                ]
            }
            (root / "ground_truth.json").write_text(
                __import__("json").dumps(truth), encoding="utf-8"
            )
            result = evaluate_assets([_finding()], str(root))
        self.assertTrue(result["available"])
        self.assertEqual(
            result["granularity"], "component_algorithm"
        )
        self.assertEqual(result["evaluation_version"], 1)
        self.assertEqual(result["precision"], 1.0)

    def test_no_ground_truth_returns_unavailable(self):
        with tempfile.TemporaryDirectory() as directory:
            result = evaluate_assets([], directory)
        self.assertFalse(result["available"])

    def test_malformed_ground_truth_returns_unavailable(self):
        for bad in (
            "not json",
            "[]",
            '{"assets":{}}',
            '{"assets":[{}]}',
            '{"assets":[{"component":[],"algorithm":"AES"}]}',
        ):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "ground_truth.json").write_text(
                    bad, encoding="utf-8"
                )
                result = evaluate_assets([], str(root))
            self.assertFalse(
                result["available"],
                f"Expected unavailable for: {bad!r}",
            )

    def test_oversized_ground_truth_returns_unavailable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "ground_truth.json").write_text(
                "x" * (3 * 1024 * 1024), encoding="utf-8"
            )
            result = evaluate_assets([], str(root))
        self.assertFalse(result["available"])


class V2AliasMatchingTests(unittest.TestCase):
    """Alias-aware matching: RSA-2048 matches RSA, etc."""

    def test_alias_match_counts_as_true_positive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            truth = _ground_truth_v2(
                assets=[{"component": "app", "algorithm": "RSA"}],
                alias_pairs=[
                    {
                        "algorithms": ["RSA", "RSA-2048"],
                        "same_family": True,
                    }
                ],
            )
            (root / "ground_truth.json").write_text(
                __import__("json").dumps(truth), encoding="utf-8"
            )
            finding = _finding(
                algorithm="RSA-2048",
                evidence_json={
                    "component": "app",
                    "usage": "encryption",
                    "key_size": 2048,
                    "operation_id": "op-1",
                    "evidence_list": [],
                },
            )
            result = evaluate_assets([finding], str(root))
        self.assertEqual(result["true_positives"], 1)
        self.assertEqual(result["precision"], 1.0)
        self.assertEqual(result["recall"], 1.0)

    def test_alias_no_match_when_component_differs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            truth = _ground_truth_v2(
                assets=[{"component": "app", "algorithm": "RSA"}],
                alias_pairs=[
                    {
                        "algorithms": ["RSA", "RSA-2048"],
                        "same_family": True,
                    }
                ],
            )
            (root / "ground_truth.json").write_text(
                __import__("json").dumps(truth), encoding="utf-8"
            )
            finding = _finding(
                algorithm="RSA-2048",
                evidence_json={
                    "component": "other",
                    "usage": "encryption",
                    "key_size": 2048,
                    "operation_id": "op-1",
                    "evidence_list": [],
                },
            )
            result = evaluate_assets([finding], str(root))
        self.assertEqual(result["true_positives"], 0)
        self.assertEqual(result["false_positives"], 1)


class V2DuplicateDetectionTests(unittest.TestCase):
    """Duplicates of the same operation must be false positives."""

    def test_two_findings_same_operation_one_fp(self):
        """When a scanner reports the same operation twice, the extra is FP."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            truth = _ground_truth_v2(
                assets=[
                    {
                        "component": "app",
                        "algorithm": "AES",
                        "usage": "encryption",
                    }
                ]
            )
            (root / "ground_truth.json").write_text(
                __import__("json").dumps(truth), encoding="utf-8"
            )
            findings = [
                _finding(
                    algorithm="AES",
                    evidence_json={
                        "component": "app",
                        "usage": "encryption",
                        "key_size": 256,
                        "operation_id": "same-op",
                        "line": 5,
                        "evidence_list": [],
                    },
                ),
                _finding(
                    algorithm="AES",
                    evidence_json={
                        "component": "app",
                        "usage": "encryption",
                        "key_size": 256,
                        "operation_id": "same-op",
                        "line": 5,
                        "evidence_list": [],
                    },
                ),
            ]
            result = evaluate_assets(findings, str(root))
        self.assertEqual(result["true_positives"], 1)
        self.assertEqual(result["false_positives"], 1)
        self.assertEqual(result["precision"], 0.5)
        self.assertEqual(result["recall"], 1.0)

    def test_three_findings_two_duplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            truth = _ground_truth_v2(
                assets=[{"component": "app", "algorithm": "RSA"}]
            )
            (root / "ground_truth.json").write_text(
                __import__("json").dumps(truth), encoding="utf-8"
            )
            same = _finding(
                algorithm="RSA",
                evidence_json={
                    "component": "app",
                    "usage": "encryption",
                    "key_size": 2048,
                    "operation_id": "dup",
                    "evidence_list": [],
                },
            )
            result = evaluate_assets(
                [same, same, same], str(root)
            )
        self.assertEqual(result["true_positives"], 1)
        self.assertEqual(result["false_positives"], 2)


class V2UsageAccuracyTests(unittest.TestCase):
    """Usage and key_size metadata accuracy scoring."""

    def test_correct_usage_is_scored(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            truth = _ground_truth_v2(
                assets=[
                    {
                        "component": "app",
                        "algorithm": "RSA",
                        "usage": "encryption",
                    }
                ]
            )
            (root / "ground_truth.json").write_text(
                __import__("json").dumps(truth), encoding="utf-8"
            )
            finding = _finding(
                evidence_json={
                    "component": "app",
                    "usage": "encryption",
                    "key_size": None,
                    "operation_id": "op-1",
                    "evidence_list": [],
                }
            )
            result = evaluate_assets([finding], str(root))
        self.assertEqual(result["usage_correct"], 1)
        self.assertEqual(result["usage_accuracy_over_expected"], 1.0)

    def test_wrong_usage_is_scored(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            truth = _ground_truth_v2(
                assets=[
                    {
                        "component": "app",
                        "algorithm": "RSA",
                        "usage": "signature",
                    }
                ]
            )
            (root / "ground_truth.json").write_text(
                __import__("json").dumps(truth), encoding="utf-8"
            )
            finding = _finding(
                evidence_json={
                    "component": "app",
                    "usage": "encryption",
                    "key_size": None,
                    "operation_id": "op-1",
                    "evidence_list": [],
                }
            )
            result = evaluate_assets([finding], str(root))
        self.assertEqual(result["usage_correct"], 0)
        self.assertEqual(result["usage_accuracy_over_expected"], 0.0)

    def test_key_size_match(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            truth = _ground_truth_v2(
                assets=[
                    {
                        "component": "app",
                        "algorithm": "RSA",
                        "usage": "encryption",
                        "key_size": 2048,
                    }
                ]
            )
            (root / "ground_truth.json").write_text(
                __import__("json").dumps(truth), encoding="utf-8"
            )
            finding = _finding(
                evidence_json={
                    "component": "app",
                    "usage": "encryption",
                    "key_size": 2048,
                    "operation_id": "op-1",
                    "evidence_list": [],
                }
            )
            result = evaluate_assets([finding], str(root))
        self.assertEqual(result["known_key_size_correct"], 1)
        self.assertEqual(
            result["known_key_size_accuracy_over_expected"], 1.0
        )

    def test_key_size_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            truth = _ground_truth_v2(
                assets=[
                    {
                        "component": "app",
                        "algorithm": "RSA",
                        "usage": "encryption",
                        "key_size": 2048,
                    }
                ]
            )
            (root / "ground_truth.json").write_text(
                __import__("json").dumps(truth), encoding="utf-8"
            )
            finding = _finding(
                evidence_json={
                    "component": "app",
                    "usage": "encryption",
                    "key_size": 4096,
                    "operation_id": "op-1",
                    "evidence_list": [],
                }
            )
            result = evaluate_assets([finding], str(root))
        self.assertEqual(result["known_key_size_correct"], 0)
        self.assertEqual(
            result["known_key_size_accuracy_over_expected"], 0.0
        )

    def test_metadata_pair_score(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            truth = _ground_truth_v2(
                assets=[
                    {
                        "component": "app",
                        "algorithm": "RSA",
                        "usage": "encryption",
                        "key_size": 2048,
                    }
                ]
            )
            (root / "ground_truth.json").write_text(
                __import__("json").dumps(truth), encoding="utf-8"
            )
            finding = _finding(
                evidence_json={
                    "component": "app",
                    "usage": "encryption",
                    "key_size": 2048,
                    "operation_id": "op-1",
                    "evidence_list": [],
                }
            )
            result = evaluate_assets([finding], str(root))
        self.assertEqual(result["metadata_pair_correct"], 1)
        self.assertEqual(
            result["metadata_pair_accuracy_over_expected"], 1.0
        )


class V2CertificateEvaluationTests(unittest.TestCase):
    """Certificate expectations from ground truth."""

    def test_no_expectations_returns_none(self):
        result = self._eval_with_certs([])
        self.assertIsNone(result.get("certificate_evaluation"))

    def test_matching_cert_is_scored(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            truth = _ground_truth_v2(
                cert_expectations=[
                    {
                        "component": "certs/server.crt",
                        "key_size": 2048,
                        "not_before": "2024-01-01",
                        "not_after": "2026-01-01",
                    }
                ]
            )
            (root / "ground_truth.json").write_text(
                __import__("json").dumps(truth), encoding="utf-8"
            )
            finding = _finding(
                source=["cert"],
                algorithm="RSA",
                evidence_json={
                    "component": "certs/server.crt",
                    "key_size": 2048,
                    "not_after": "2026-01-01",
                    "subject_cn": "server",
                    "serial_number": "1",
                    "evidence_list": [],
                },
            )
            result = evaluate_assets([finding], str(root))
        cert = result["certificate_evaluation"]
        self.assertEqual(cert["matched"], 1)
        self.assertEqual(cert["certificate_accuracy"], 1.0)
        self.assertEqual(cert["mismatches"], [])

    def test_key_size_mismatch_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            truth = _ground_truth_v2(
                cert_expectations=[
                    {
                        "component": "certs/server.crt",
                        "key_size": 2048,
                        "not_before": "2024-01-01",
                        "not_after": "2026-01-01",
                    }
                ]
            )
            (root / "ground_truth.json").write_text(
                __import__("json").dumps(truth), encoding="utf-8"
            )
            finding = _finding(
                source=["cert"],
                algorithm="RSA",
                evidence_json={
                    "component": "certs/server.crt",
                    "key_size": 4096,
                    "not_after": "2026-01-01",
                    "subject_cn": "server",
                    "serial_number": "1",
                    "evidence_list": [],
                },
            )
            result = evaluate_assets([finding], str(root))
        cert = result["certificate_evaluation"]
        self.assertEqual(cert["matched"], 0)
        self.assertEqual(len(cert["mismatches"]), 1)
        self.assertIn(
            "key_size mismatch", cert["mismatches"][0]["issue"]
        )

    def test_missing_cert_is_false_negative(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            truth = _ground_truth_v2(
                cert_expectations=[
                    {
                        "component": "certs/server.crt",
                        "key_size": 2048,
                        "not_before": "2024-01-01",
                        "not_after": "2026-01-01",
                    }
                ]
            )
            (root / "ground_truth.json").write_text(
                __import__("json").dumps(truth), encoding="utf-8"
            )
            result = evaluate_assets([], str(root))
        cert = result["certificate_evaluation"]
        self.assertEqual(cert["matched"], 0)
        self.assertEqual(len(cert["mismatches"]), 1)
        self.assertEqual(
            cert["mismatches"][0]["issue"],
            "certificate_not_found",
        )

    def _eval_with_certs(self, expectations):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            truth = _ground_truth_v2(
                cert_expectations=expectations
            )
            (root / "ground_truth.json").write_text(
                __import__("json").dumps(truth), encoding="utf-8"
            )
            return evaluate_assets([], str(root))


class V2PerSourceTests(unittest.TestCase):
    """Per-source precision/recall breakdown in v2 mode."""

    def test_per_source_breakdown(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            truth = _ground_truth_v2(
                assets=[{"component": "app", "algorithm": "AES"}]
            )
            (root / "ground_truth.json").write_text(
                __import__("json").dumps(truth), encoding="utf-8"
            )
            findings = [_finding()]
            result = evaluate_assets(findings, str(root))
        self.assertIn("rule", result["per_source"])
        self.assertEqual(result["per_source"]["rule"]["findings"], 1)
        self.assertEqual(
            result["per_source"]["rule"]["true_positives"], 1
        )


class V2BlindSpotsTests(unittest.TestCase):
    """Blind spots from ground truth are propagated."""

    def test_blind_spots_included(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            truth = _ground_truth_v2(
                assets=[{"component": "app", "algorithm": "AES"}],
                blind_spots=[
                    {
                        "component": "blind-spot",
                        "algorithm": "AES",
                        "reason": "runtime-computed module",
                    }
                ],
            )
            (root / "ground_truth.json").write_text(
                __import__("json").dumps(truth), encoding="utf-8"
            )
            result = evaluate_assets([_finding()], str(root))
        self.assertEqual(len(result["declared_blind_spots"]), 1)
        self.assertEqual(
            result["declared_blind_spots"][0]["reason"],
            "runtime-computed module",
        )


if __name__ == "__main__":
    unittest.main()
