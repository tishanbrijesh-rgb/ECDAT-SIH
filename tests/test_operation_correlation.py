"""Operation boundaries and determinism, independent of demo counts."""
import itertools
import unittest

from backend.services.correlator import correlate
from backend.services.risk_engine import assess_risk


def record(usage="unknown", operation="op", location="test-repo/app/a.py", **details):
    return {"algorithm": "RSA", "category": "encryption", "source": "rule",
            "location": location, "confidence": 0.82,
            "evidence": {"usage": usage, "operation_id": operation, **details}}


def findings(records):
    return correlate({"records": records})


class OperationCorrelationTests(unittest.TestCase):
    def test_distinct_usages_and_unknown_remain_separate(self):
        result = findings([record(u) for u in ("signature", "encryption", "key_establishment", "unknown")])
        self.assertEqual({f["usage"] for f in result}, {"signature", "encryption", "key_establishment", "unknown"})
        self.assertEqual(len({f["logical_asset_id"] for f in result}), 4)
        for f in result:
            recommendation = assess_risk(f)["pqc_candidate"]
            if f["usage"] == "signature":
                self.assertIn("ML-DSA", recommendation)
            elif f["usage"] == "unknown":
                self.assertNotIn("ML-KEM", recommendation)

    def test_different_operations_and_files_do_not_merge(self):
        self.assertEqual(len(findings([record("signature", "one"), record("signature", "two"),
                                      record("signature", "one", "test-repo/app/b.py")])), 3)

    def test_every_input_permutation_has_identical_output(self):
        records = [record("signature", key_size=2048), record("encryption", key_size=4096),
                   record("signature", key_size=3072)]
        baseline = findings(records)
        for permutation in itertools.permutations(records):
            self.assertEqual(findings(list(permutation)), baseline)

    def test_conflicting_metadata_is_not_arbitrarily_selected(self):
        result = findings([record("signature", key_size=2048), record("signature", key_size=4096)])[0]
        self.assertIsNone(result["key_size"])
        self.assertTrue(result["conflict"])
        self.assertEqual(result["context_conflicts"]["key_size"], [2048, 4096])

    def test_same_operation_agreement_combines_sources(self):
        first = record("signature")
        second = {**first, "source": "ast", "confidence": 0.9}
        result = findings([first, second])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["sources"], ["ast", "rule"])

    def test_operation_ids_are_scoped_to_files(self):
        first = record("encryption")
        second = {**record("encryption", location="test-repo/app/b.py"), "algorithm": "AES"}
        self.assertFalse(any(f["conflict"] for f in findings([first, second])))

    def test_same_operation_algorithm_disagreement_is_retained(self):
        first = record("encryption")
        self.assertTrue(all(f["conflict"] for f in findings([first, {**first, "algorithm": "AES"}])))

    def test_ids_ignore_random_evidence_ids(self):
        self.assertEqual(findings([{**record(), "asset_id": "a"}])[0]["logical_asset_id"],
                         findings([{**record(), "asset_id": "b"}])[0]["logical_asset_id"])

    def test_line_fallback_preserves_separate_operations(self):
        first = record("signature", None, line=10)
        second = record("signature", None, line=20)
        self.assertEqual(len(findings([first, second])), 2)

    def test_category_does_not_override_explicit_or_unknown_usage(self):
        first = {**record("encryption"), "category": "signature"}
        second = {**record(), "category": "signature"}
        self.assertEqual({f["usage"] for f in findings([first, second])}, {"encryption", "unknown"})
