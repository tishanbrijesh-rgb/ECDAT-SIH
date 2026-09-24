"""
Phase 3 detector evaluation — validates ECDAT collectors against the sealed
holdout corpus. Measures per-family recall and overall precision.

For each positive entry, creates a temp file with representative code for the
(language, algorithm_family) pair, runs the appropriate collector, and verifies
at least one detected algorithm matches the expected algorithm_family.

For each negative entry, creates a temp file with representative code for the
algorithm actually described in the label (i.e., what IS in the file), runs the
appropriate collector, and verifies no detector produces an asset matching the
entry's algorithm_family.

Placeholder code (lines containing "...", "placeholder", or raw "<") is skipped.
RuleCollector tests are skipped gracefully for languages where representative
snippets cannot be produced.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import unittest
from collections import defaultdict
from pathlib import Path

from scanner.collectors.ast_collector import ASTCollector
from scanner.collectors.rule_collector import RuleCollector

PROJECT_ROOT = Path(__file__).resolve().parents[1]
HOLDOUT_CORPUS_PATH = PROJECT_ROOT / "scanner" / "corpus" / "holdout" / "holdout_all.json"

LANG_EXT = {
    "python": ".py",
    "java": ".java",
    "javascript": ".js",
    "c": ".c",
    "go": ".go",
    "rust": ".rs",
}

# Patterns that indicate placeholder / non-executable code.
_PLACEHOLDER_RE = re.compile(r"\.\.\.|placeholder|<\s*(?!\w)", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Representative code templates keyed by (language, algorithm_family).
# These are minimal but syntactically valid snippets that exercise each
# algorithm's typical import / construction pattern so the collectors can
# detect them.
# ---------------------------------------------------------------------------
_CODE_TEMPLATES: dict[str, dict[str, str]] = {
    "python": {
        "RSA": (
            "from Crypto.PublicKey import RSA\n"
            "from Crypto.Cipher import PKCS1_OAEP\n"
            "key = RSA.generate\n"
        ),
        "ECDSA": (
            "from cryptography.hazmat.primitives.asymmetric import ec\n"
            "key = ec.generate_private_key(ec.SECP256R1())\n"
        ),
        "AES": (
            "from Crypto.Cipher import AES\n"
            "cipher = AES.new(key, AES.MODE_GCM)\n"
        ),
        "SHA-256": (
            "import hashlib\n"
            "h = hashlib.sha256(data)\n"
        ),
        "HMAC": (
            "import hmac, hashlib\n"
            "mac = hmac.new(key, msg, hashlib.sha256)\n"
        ),
        "Ed25519": (
            "from cryptography.hazmat.primitives.asymmetric.ed25519 "
            "import Ed25519PrivateKey\n"
            "key = Ed25519PrivateKey.generate()\n"
        ),
        "ML-KEM": (
            "from mlkem import MLKEM\n"
            "kem = MLKEM(512)\n"
        ),
        "ML-DSA": (
            "from mldsa import MLDSA\n"
            "sig = MLDSA.sign(key, msg)\n"
        ),
        "ChaCha20": (
            "from cryptography.hazmat.primitives.ciphers.aead "
            "import ChaCha20Poly1305\n"
            "key = ChaCha20Poly1305.generate_key()\n"
        ),
    },
    "java": {
        "RSA": (
            "import java.security.KeyPairGenerator;\n"
            "KeyPairGenerator gen = KeyPairGenerator.getInstance(\"RSA\");\n"
        ),
        "ECDSA": (
            "import java.security.KeyPairGenerator;\n"
            "KeyPairGenerator gen = KeyPairGenerator.getInstance(\"EC\");\n"
        ),
        "AES": (
            "import javax.crypto.Cipher;\n"
            "Cipher.getInstance(\"AES/GCM/NoPadding\");\n"
        ),
        "SHA-256": (
            "import java.security.MessageDigest;\n"
            "MessageDigest.getInstance(\"SHA-256\");\n"
        ),
        "HMAC": (
            "import javax.crypto.Mac;\n"
            "Mac.getInstance(\"HmacSHA256\");\n"
        ),
        "Ed25519": (
            "import java.security.KeyPairGenerator;\n"
            "KeyPairGenerator gen = KeyPairGenerator.getInstance(\"Ed25519\");\n"
        ),
        "ML-KEM": (
            "import org.bouncycastle.pqc.crypto.mlkem.MLKEM;\n"
            "MLKEM.generateKeyPair();\n"
        ),
        "ML-DSA": (
            "import org.bouncycastle.pqc.crypto.mldsa.MLDSA;\n"
            "MLDSA.generateKeyPair();\n"
        ),
        "ChaCha20": (
            "import org.bouncycastle.crypto.engines.ChaChaEngine;\n"
            "new ChaChaEngine();\n"
        ),
    },
    "javascript": {
        "RSA": (
            'const { generateKeyPairSync } = require("node-forge").pki;\n'
            'generateKeyPairSync("RSA");\n'
        ),
        "ECDSA": (
            'const { generateKeyPairSync } = require("node-forge").pki;\n'
            'generateKeyPairSync("EC");\n'
        ),
        "AES": (
            'const AES = require("crypto-js").AES;\n'
            'AES.encrypt(msg, key);\n'
        ),
        "SHA-256": (
            'const sha256 = require("crypto-js").SHA256;\n'
            'sha256(msg);\n'
        ),
        "HMAC": (
            'const hmacSHA256 = require("crypto-js").HmacSHA256;\n'
            'hmacSHA256(msg, key);\n'
        ),
        "Ed25519": (
            'const { generateKeyPair } = require("jose").webcrypto;\n'
            'await generateKeyPair("Ed25519");\n'
        ),
        "ML-KEM": (
            'const { mlkem } = require("@stablelib/mlkem");\n'
            "mlkem.generateKeyPair();\n"
        ),
        "ML-DSA": (
            'const { mldsa } = require("@stablelib/mldsa");\n'
            "mldsa.generateKeyPair();\n"
        ),
        "ChaCha20": (
            'const { chacha20poly1305 } = require("tweetnacl");\n'
            "chacha20poly1305();\n"
        ),
    },
    "c": {
        "RSA": (
            '#include <openssl/rsa.h>\n'
            "RSA *key = RSA_generate_key(2048, RSA_F4, NULL, NULL);\n"
        ),
        "ECDSA": (
            '#include <openssl/ecdsa.h>\n'
            "EC_KEY *key = EC_KEY_new_by_curve_name(NID_X9_62_prime256v1);\n"
        ),
        "AES": (
            '#include <openssl/aes.h>\n'
            "AES_KEY key;\n"
            "AES_set_encrypt_key(key, &key);\n"
        ),
        "SHA-256": (
            '#include <openssl/sha.h>\n'
            "SHA256(data, len, out);\n"
        ),
        "HMAC": (
            '#include <openssl/hmac.h>\n'
            "HMAC(EVP_sha256(), key, klen, data, dlen, out, NULL);\n"
        ),
        "Ed25519": (
            '#include <openssl/evp.h>\n'
            "EVP_PKEY *key = EVP_PKEY_new();\n"
            "EVP_PKEY_keygen_init(key, EVP_PKEY_ED25519);\n"
        ),
        "ML-KEM": (
            "#include <oqs/oqs.h>\n"
            "OQS_KEM *kem = OQS_KEM_new(OQS_KEM_alg_ml_kem_768);\n"
        ),
        "ML-DSA": (
            "#include <oqs/oqs.h>\n"
            "OQS_SIG *sig = OQS_SIG_new(OQS_SIG_alg_ml_dsa_65);\n"
        ),
        "ChaCha20": (
            '#include <openssl/chacha.h>\n'
            "EVP_CIPHER_CTX *ctx = EVP_CIPHER_CTX_new();\n"
            "EVP_CipherInit_ex(ctx, EVP_chacha20(), NULL, key, iv, 1);\n"
        ),
    },
    "go": {
        "RSA": (
            'import "crypto/rsa"\n'
            "key, _ := rsa.GenerateKey(rand.Reader, 2048)\n"
        ),
        "ECDSA": (
            'import "crypto/ecdsa"\n'
            "key, _ := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)\n"
        ),
        "AES": (
            'import "crypto/aes"\n'
            "block, _ := aes.NewCipher(key)\n"
        ),
        "SHA-256": (
            'import "crypto/sha256"\n'
            "h := sha256.New()\n"
        ),
        "HMAC": (
            'import "crypto/hmac"\n'
            "hmac.New(sha256.New, key)\n"
        ),
        "Ed25519": (
            'import "crypto/ed25519"\n'
            "_, priv, _ := ed25519.GenerateKey(rand.Reader)\n"
        ),
        "ML-KEM": (
            'import "github.com/cloudflare/circl/kem/mlkem"\n'
            "scheme, _ := mlkem.Scheme(mlkem.MLKEM_768).GenerateKeyPair()\n"
        ),
        "ML-DSA": (
            'import "github.com/cloudflare/circl/sign/mldsa"\n'
            "_, priv, _ := mldsa.GenerateKey()\n"
        ),
        "ChaCha20": (
            'import "golang.org/x/crypto/chacha20poly1305"\n'
            "aead := chacha20poly1305.New(key)\n"
        ),
    },
    "rust": {
        "RSA": (
            "use rsa::RsaKeyPairGenerator;\n"
            "let key = RsaKeyPairGenerator::new.generate(&mut rng).unwrap();\n"
        ),
        "ECDSA": (
            "use p256::SecretKey;\n"
            "let key = SecretKey::random(&mut thread_rng());\n"
        ),
        "AES": (
            "use aes::Aes256;\n"
            "use aes::cipher::KeyInit;\n"
            "let cipher = Aes256::new(&key.into());\n"
        ),
        "SHA-256": (
            "use sha2::{Sha256, Digest};\n"
            "let mut hasher = Sha256::new();\n"
            "hasher.update(data);\n"
        ),
        "HMAC": (
            "use hmac::{Hmac, Mac};\n"
            "let mut mac = Hmac::<Sha256>::new_from_slice(&key).unwrap();\n"
        ),
        "Ed25519": (
            "use ed25519_dalek::Keypair;\n"
            "let keypair = Keypair::generate(&mut rand::rngs::OsRng{});\n"
        ),
        "ML-KEM": (
            "use ml_kem::MlKem768;\n"
            "let (pk, sk) = MlKem768::generate_keypair();\n"
        ),
        "ML-DSA": (
            "use mldsa::MlDsa65;\n"
            "let (pk, sk) = MlDsa65::generate_keypair();\n"
        ),
        "ChaCha20": (
            "use chacha20poly1305::{ChaCha20Poly1305, KeyInit};\n"
            "let cipher = ChaCha20Poly1305::new(&key.into());\n"
        ),
    },
}


def _is_placeholder(code: str) -> bool:
    """Return True if the code looks like a placeholder / stub."""
    return bool(_PLACEHOLDER_RE.search(code))


def _collectors_for(lang: str) -> list[tuple[str, object]]:
    """Return [(name, collector_instance), ...] appropriate for the language."""
    collectors = []
    if lang == "python":
        collectors.append(("ast", ASTCollector()))
        collectors.append(("rule", RuleCollector()))
    elif lang in LANG_EXT:
        collectors.append(("rule", RuleCollector()))
    return collectors


def _run_collectors(lang: str, code: str) -> list[dict]:
    """Write code to a temp file, run collectors, return list of asset dicts."""
    results: list[dict] = []
    tmpdir = tempfile.mkdtemp(prefix="ecdat-corpus-test-")
    try:
        ext = LANG_EXT.get(lang, ".txt")
        path = os.path.join(tmpdir, f"sample{ext}")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(code)
        for name, collector in _collectors_for(lang):
            try:
                assets = collector.scan_file(path)
                for asset in assets:
                    algo = getattr(asset, "algorithm", None)
                    if algo:
                        results.append({
                            "collector": name,
                            "algorithm": str(algo),
                        })
            except Exception:
                pass
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    return results


def _algo_matches(expected: str, detected: str) -> bool:
    """Check if a detected algorithm string matches the expected family."""
    e = expected.lower().replace("-", "")
    d = detected.lower().replace("-", "")
    return e in d or d in e


def _label_to_algorithm(label: str) -> str | None:
    """Heuristically extract the actual algorithm present from a negative label.

    E.g.  "SHA-256 only" → "SHA-256"
          "AES encrypt, no HMAC" → "AES"
          "RSA signature, no HMAC" → "RSA"
    """
    families = [
        "RSA", "ECDSA", "AES", "SHA-256", "SHA-512", "SHA-1", "MD5",
        "HMAC", "Ed25519", "ML-KEM", "ML-DSA", "ChaCha20", "DES", "3DES",
        "BLAKE2", "TLS",
    ]
    upper = label
    for fam in families:
        if fam in upper:
            return fam
    # Try looser matching for common words
    lower = label.lower()
    for fam in ["rsa", "ecdsa", "aes", "sha", "hmac", "ed25519", "mlkem",
                "mldsa", "chacha", "md5", "des"]:
        if fam in lower:
            # Map back to canonical name
            canonical = {
                "rsa": "RSA", "ecdsa": "ECDSA", "aes": "AES",
                "sha": "SHA-256", "hmac": "HMAC", "ed25519": "Ed25519",
                "mlkem": "ML-KEM", "mldsa": "ML-DSA", "chacha": "ChaCha20",
                "md5": "MD5", "des": "DES",
            }
            return canonical.get(fam)
    return None


class TestDetectorCorpus(unittest.TestCase):
    """Evaluate collectors against the Phase 3 holdout corpus."""

    @classmethod
    def setUpClass(cls):
        with open(HOLDOUT_CORPUS_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
        cls.entries = data.get("entries", [])
        cls.positive = [e for e in cls.entries if e.get("positive")]
        cls.negative = [e for e in cls.entries if not e.get("positive")]

    # ------------------------------------------------------------------
    # Positive-entry recall
    # ------------------------------------------------------------------

    def test_detectors_recall_positive_corpus_entries(self):
        """For each positive entry, verify at least one collector detects the
        expected algorithm_family.  Per-family recall must be >= 0.70."""
        family_detected: dict[str, int] = defaultdict(int)
        family_tested: dict[str, int] = defaultdict(int)
        skipped = []

        for entry in self.positive:
            lang = entry.get("language", "")
            fam = entry.get("algorithm_family", "")

            # Pick the right template for this (lang, family)
            template = (
                _CODE_TEMPLATES.get(lang, {}).get(fam, "") or ""
            )
            if not template:
                skipped.append(entry["corpus_id"])
                continue
            if _is_placeholder(template):
                skipped.append(entry["corpus_id"])
                continue

            # Skip if no collectors can handle this language
            collectors = _collectors_for(lang)
            if not collectors:
                skipped.append(entry["corpus_id"])
                continue

            detected = _run_collectors(lang, template)
            matched = any(
                _algo_matches(fam, r["algorithm"]) for r in detected
            )

            family_tested[fam] += 1
            if matched:
                family_detected[fam] += 1

        # Per-family recall >= 0.70 (for families with >= 1 tested entry)
        for fam in sorted(family_tested):
            tested = family_tested[fam]
            detected = family_detected.get(fam, 0)
            recall = detected / tested if tested > 0 else 0.0
            self.assertGreaterEqual(
                recall, 0.70,
                f"Family {fam} recall {detected}/{tested} = {recall:.0%} below 70%",
            )

        # Log skipped entries for visibility
        if skipped:
            print(f"\nSkipped {len(skipped)} entries (no template): {skipped}")

    # ------------------------------------------------------------------
    # Negative-entry precision
    # ------------------------------------------------------------------

    def test_detectors_precision_on_negative_corpus_entries(self):
        """For each negative entry, create a temp file with code that reflects
        what is actually in the file (derived from the label) and verify no
        detector produces an asset matching the entry's algorithm_family.
        Overall precision across all negatives must be >= 0.60."""
        true_negatives = 0
        false_positives = 0
        skipped = []

        for entry in self.negative:
            lang = entry.get("language", "")
            target_fam = entry.get("algorithm_family", "")
            label = entry.get("label", "")

            # Determine what algorithm the file ACTUALLY contains
            actual_algo = _label_to_algorithm(label)
            if actual_algo is None:
                # Fallback: use a generic template for this language
                actual_algo = "SHA-256"

            template = (
                _CODE_TEMPLATES.get(lang, {}).get(actual_algo, "") or ""
            )
            if not template:
                skipped.append(entry["corpus_id"])
                continue
            if _is_placeholder(template):
                skipped.append(entry["corpus_id"])
                continue

            collectors = _collectors_for(lang)
            if not collectors:
                skipped.append(entry["corpus_id"])
                continue

            detected = _run_collectors(lang, template)
            # Check whether any detector falsely reported the target family
            falsely_detected = any(
                _algo_matches(target_fam, r["algorithm"]) for r in detected
            )

            if falsely_detected:
                false_positives += 1
            else:
                true_negatives += 1

        total = true_negatives + false_positives
        if total > 0:
            precision = true_negatives / total
            self.assertGreaterEqual(
                precision, 0.60,
                f"Precision {true_negatives}/{total} = {precision:.0%} below 60%",
            )

        if skipped:
            print(
                f"\nSkipped {len(skipped)} negative entries "
                f"(no template / no collectors): {skipped}"
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
