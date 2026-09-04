"""Adversarial regression corpus; not an independent real-world benchmark."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from scanner.main import scan_with_metrics
from backend.services.correlator import correlate
from backend.services.evaluation import evaluate_assets


CASES = [
    ("hash.py", "import hashlib\nhashlib.sha256(b'data')\n", {"SHA-256"}),
    ("md5.py", "import hashlib\nhashlib.md5(b'data')\n", {"MD5"}),
    ("aes.py", "from Crypto.Cipher import AES\nAES.new(key, AES.MODE_GCM)\n", {"AES"}),
    ("comment.py", "# hashlib.sha256(b'data')\n", set()),
    ("text.py", "print('sha256 is a word, not a crypto call')\n", set()),
    ("padding.py", "print('padding')\n", set()),
    ("url.java", 'String url="https://example.test"; Cipher.getInstance("AES/GCM/NoPadding");', {"AES"}),
    ("comment.java", "/* Cipher.getInstance(\"AES\"); */", set()),
]


def measure():
    tp = fp = fn = 0
    mismatches = []
    with tempfile.TemporaryDirectory() as directory:
        for filename, source, expected in CASES:
            root = Path(directory) / filename.replace(".", "_")
            root.mkdir()
            (root / filename).write_text(source, encoding="utf-8")
            evidence, _ = scan_with_metrics(str(root))
            actual = {item["algorithm"] for item in correlate(evidence)}
            tp += len(actual & expected)
            fp += len(actual - expected)
            fn += len(expected - actual)
            if actual != expected:
                mismatches.append((filename, sorted(expected), sorted(actual)))
    return {"cases": len(CASES), "true_positives": tp, "false_positives": fp,
            "false_negatives": fn, "precision": tp / (tp + fp) if tp + fp else 0,
            "recall": tp / (tp + fn) if tp + fn else 1, "mismatches": mismatches}


class PrecisionTests(unittest.TestCase):
    def test_adversarial_regression_corpus(self):
        self.assertEqual(measure()["mismatches"], [])

    def test_malformed_ground_truth_is_unavailable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ground_truth.json"
            for value in ("not json", "[]", '{"assets":[{}]}', '{"assets":"wrong"}',
                          '{"assets":[{"component":[],"algorithm":"AES"}]}'):
                path.write_text(value, encoding="utf-8")
                self.assertFalse(evaluate_assets([], directory)["available"])

    def test_evaluation_counts_false_positives_and_negatives(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "ground_truth.json").write_text(
                '{"assets":[{"component":"app","algorithm":"AES"},'
                '{"component":"app","algorithm":"RSA"}]}', encoding="utf-8")
            assets = [SimpleNamespace(evidence_json={"component": "app"},
                      algorithm=algorithm, source=["rule"], location="app/a.py")
                      for algorithm in ("AES", "MD5")]
            result = evaluate_assets(assets, directory)
            self.assertEqual((result["true_positives"], result["false_positives"],
                              result["false_negatives"]), (1, 1, 1))
            self.assertEqual((result["precision"], result["recall"]), (0.5, 0.5))

    def test_parser_errors_reduce_coverage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for filename, source in (("bad.py", "def broken(:"),
                                     ("pom.xml", "<project>"), ("bad.cer", "not PEM"),
                                     ("good.py", "x = 1")):
                (root / filename).write_text(source, encoding="utf-8")
            _, metrics = scan_with_metrics(directory)
            self.assertEqual(metrics["failed_files"], 3)
            self.assertEqual(metrics["scanned_files"], 1)
            self.assertEqual(metrics["coverage_pct"], 25.0)


if __name__ == "__main__":
    print(measure())
