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


CHALLENGE_CASES = [
    ("direct.py", 'import hashlib\nhashlib.sha256(b"x")', {"SHA-256"}),
    ("alias.py", 'import hashlib as h\nh.sha256(b"x")', {"SHA-256"}),
    ("from.py", 'from hashlib import sha256\nsha256(b"x")', {"SHA-256"}),
    ("upper.py", 'import hashlib\nhashlib.new("SHA256", b"x")', {"SHA-256"}),
    ("padding.py", 'def padding(x): return x\npadding(4)', set()),
    ("shadow.py", 'class Demo:\n def sha256(self,x): return x\nhashlib = Demo()\nhashlib.sha256(b"x")', set()),
    ("text.java", 'System.out.println("Cipher.getInstance(\\"AES\\")");', set()),
    ("aes.java", 'Cipher.getInstance("AES/GCM/NoPadding");', {"AES"}),
    ("dynamic.py", 'import hashlib\ngetattr(obj,"name"); hashlib.sha256(b"x")', {"SHA-256"}),
    ("comment.py", '# hashlib.md5(b"x")', set()),
    ("md5.py", 'import hashlib\nhashlib.md5(b"x")', {"MD5"}),
    ("new.py", 'import hashlib\nhashlib.new("sha256", b"x")', {"SHA-256"}),
]


def measure(cases=CASES):
    tp = fp = fn = 0
    mismatches = []
    with tempfile.TemporaryDirectory() as directory:
        for filename, source, expected in cases:
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
    return {"cases": len(cases), "true_positives": tp, "false_positives": fp,
            "false_negatives": fn, "precision": tp / (tp + fp) if tp + fp else 0,
            "recall": tp / (tp + fn) if tp + fn else 1, "mismatches": mismatches}


class PrecisionTests(unittest.TestCase):
    def scan_fixture(self, source, filename="example.py"):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / filename).write_text(source, encoding="utf-8")
            evidence, metrics = scan_with_metrics(directory)
            return correlate(evidence), metrics

    def test_expanded_challenge_corpus(self):
        result = measure(CHALLENGE_CASES)
        self.assertEqual(result["mismatches"], [])
        self.assertEqual((result["true_positives"], result["false_positives"],
                          result["false_negatives"]), (8, 0, 0))

    def test_hash_bindings_and_scope(self):
        cases = [
            ('import hashlib as h\nh = object()\nh.sha256(b"x")', 0),
            ('from hashlib import sha256 as digest\ndigest(b"x")', 1),
            ('from hashlib import sha256\ndef sha256(x): return x\nsha256(b"x")', 0),
            ('import hashlib\ndef f(hashlib): return hashlib.sha256(b"x")', 0),
            ('import hashlib\nf = lambda hashlib: hashlib.sha256(b"x")', 0),
            ('import hashlib\ndef f():\n hashlib.sha256(b"x")\n hashlib = object()', 0),
            ('import hashlib\ndef f():\n hashlib = object()\n return hashlib.sha256(b"x")\nhashlib.sha256(b"y")', 1),
            ('import hashlib\nhashlib.sha256 = lambda x: x\nhashlib.sha256(b"x")', 0),
            ('import hashlib\nhashlib.new(name="SHA-256", data=b"x")', 1),
            ('import hashlib\nhashlib.new("sha256-not-an-algorithm", b"x")', 0),
            ('import hashlib\n[hashlib.sha256(b"x") for hashlib in values]', 0),
            ('import hashlib\ndef f():\n [hashlib for hashlib in values]\n return hashlib.sha256(b"x")', 1),
            ('import hashlib\nfrom . import hashlib\nhashlib.sha256(b"x")', 0),
            ('import hashlib, hmac\nhmac.new(key, data, hashlib.sha256)', 1),
            ('import hashlib, hmac\nhmac.new(key, data, digestmod="SHA256")', 1),
        ]
        for source, count in cases:
            with self.subTest(source=source):
                findings, _ = self.scan_fixture(source)
                self.assertEqual(len(findings), count)

    def test_single_hash_call_is_not_double_counted(self):
        findings, _ = self.scan_fixture('import hashlib\nhashlib.sha256(b"x")')
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["usage"], "hashing")
        self.assertEqual(findings[0]["sources"], ["ast"])

    def test_two_hash_calls_on_one_line_stay_separate(self):
        findings, _ = self.scan_fixture('import hashlib\nhashlib.sha256(b"x"); hashlib.sha256(b"y")')
        self.assertEqual(len(findings), 2)
        self.assertEqual(len({f["logical_asset_id"] for f in findings}), 2)

    def test_key_size_requires_algorithm_specific_argument(self):
        for bits in (128, 192, 256):
            with self.subTest(bits=bits):
                findings, _ = self.scan_fixture(
                    f'KeyGenerator.getInstance("AES").init({bits});', "example.java")
                self.assertEqual(findings[0]["key_size"], bits)
        for source in ('int count=2048; Cipher.getInstance("AES/GCM/NoPadding");',
                       'KeyGenerator.getInstance("AES").init(2048);'):
            findings, _ = self.scan_fixture(source, "example.java")
            self.assertIsNone(findings[0]["key_size"])

    def test_same_line_rule_operations_do_not_share_key_sizes(self):
        findings, _ = self.scan_fixture(
            'KeyGenerator.getInstance("AES").init(256); Cipher.getInstance("AES/GCM/NoPadding");',
            "example.java")
        self.assertEqual(len(findings), 2)
        self.assertEqual({f["key_size"] for f in findings}, {256, None})

    def test_literals_are_not_executable_crypto(self):
        for source in ('String text = "AES RSA SHA256";',
                       'String text = """\nCipher.getInstance("AES");\n""";',
                       'const text = `Cipher.getInstance("AES")`;'):
            findings, _ = self.scan_fixture(source, "example.java")
            self.assertEqual(findings, [])

    def test_empty_scope_does_not_claim_full_coverage(self):
        findings, metrics = self.scan_fixture("plain text", "readme.txt")
        self.assertEqual(findings, [])
        self.assertEqual(metrics["coverage_pct"], 0.0)
        self.assertTrue(any("No supported files" in gap for gap in metrics["blind_spots"]))

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
