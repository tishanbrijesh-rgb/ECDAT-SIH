"""
AST-based static analysis collector. Walks Python AST to detect
cryptographic imports, function calls, and variable assignments.
"""

from __future__ import annotations

import ast
import os
from dataclasses import dataclass
from typing import Any

from scanner.models.asset import CryptoAsset
from scanner.rules.crypto_patterns import get_category

# ---------------------------------------------------------------------------
# Known crypto library imports mapped to algorithms
# ---------------------------------------------------------------------------
_CRYPTO_IMPORTS: dict[str, str] = {
    # PyCryptodome / PyCrypto
    "Crypto.Cipher.AES": "AES",
    "Crypto.Cipher.PKCS1_OAEP": "RSA",
    "Crypto.Cipher._mode_gcm.GcmMode": "AES",
    "Crypto.Cipher._mode_cbc.CbcMode": "AES",
    "Crypto.Cipher.DES3": "3DES",
    "Crypto.Signature.PKCS1_v1_5": "RSA",
    "Crypto.PublicKey.RSA": "RSA",
    "Crypto.PublicKey.ECC": "ECDSA",
    "Crypto.Hash.SHA256": "SHA-256",
    "Crypto.Hash.SHA512": "SHA-512",
    "Crypto.Hash.MD5": "MD5",
    "Crypto.Hash.BLAKE2": "BLAKE2",
    "Crypto.Signature.ed25519": "Ed25519",
    "Crypto.Random": "RNG",
    # cryptography library
    "cryptography.hazmat.primitives.ciphers": "AES",
    "cryptography.hazmat.primitives.ciphers.modes": "AES",
    "cryptography.hazmat.primitives.ciphers.algorithms": "AES",
    "cryptography.hazmat.primitives.asymmetric.rsa": "RSA",
    "cryptography.hazmat.primitives.asymmetric.ec": "ECDSA",
    "cryptography.hazmat.primitives.asymmetric.padding": "RSA",
    "cryptography.hazmat.primitives.asymmetric.ed25519": "Ed25519",
    "cryptography.hazmat.primitives.kdf": "KDF",
    # ssl / cryptography.x509
    "ssl": "TLS",
    "cryptography.x509": "X509",
}

# Call-patterns -> (algorithm, category)
_CALL_PATTERNS: dict[str, tuple[str, str]] = {
    # Cipher.getInstance style
    "AES/GCM": ("AES", "encryption"),
    "AES/CBC": ("AES", "encryption"),
    "RSA/ECB/PKCS1Padding": ("RSA", "encryption"),
    "RSA/ECB/OAEPWithSHA-1AndMGF1Padding": ("RSA", "encryption"),
    # hashlib calls
    "sha256": ("SHA-256", "hash"),
    "sha512": ("SHA-512", "hash"),
    "md5": ("MD5", "hash"),
    "blake2b": ("BLAKE2", "hash"),
    "blake2s": ("BLAKE2", "hash"),
    "sha1": ("SHA-1", "hash"),
    # cryptography.hazmat call patterns
    "from cryptography.hazmat.primitives.asymmetric.rsa": ("RSA", "encryption"),
    "from cryptography.hazmat.primitives.asymmetric.ec": ("ECDSA", "signature"),
    "from cryptography.hazmat.primitives.asymmetric.ed25519": ("Ed25519", "signature"),
    "OAEP": ("RSA", "encryption"),
    "PKCS1v15": ("RSA", "encryption"),
    "padding": ("RSA", "encryption"),
    # PKCS1_OAEP.new
    "PKCS1_OAEP": ("RSA", "encryption"),
}


class _CryptoVisitor(ast.NodeVisitor):
    """Walks AST nodes and records crypto-related findings."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.assets: list[CryptoAsset] = []

    # ---- import handling ---------------------------------------------------

    def _record_import(self, full_name: str, node: ast.AST, line_no: int) -> None:
        algo = _CRYPTO_IMPORTS.get(full_name)
        if algo is None:
            return
        cat = "hash" if algo == "hash" else get_category(algo)
        evidence = {
            "import": full_name,
            "node_type": type(node).__name__,
            "line": line_no,
        }
        self.assets.append(
            CryptoAsset(
                algorithm=algo,
                category=cat,
                source="ast",
                location=self.filepath,
                evidence=evidence,
                confidence=0.90,
            )
        )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802
        if node.module is not None:
            full_name = node.module
            self._record_import(full_name, node, node.lineno)
            # Also check submodule imports  e.g. from cryptography.hazmat... import X
            for alias in node.names:
                sub = f"{full_name}.{alias.name}"
                self._record_import(sub, node, node.lineno)
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:  # noqa: N802
        for alias in node.names:
            self._record_import(alias.name, node, node.lineno)
        self.generic_visit(node)

    # ---- call handling -----------------------------------------------------

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        # Reconstruct call string: func.func.attr or func.id
        func_name = ""
        if isinstance(node.func, ast.Attribute):
            # Walk to root
            parts: list[str] = []
            cur: ast.expr = node.func
            while isinstance(cur, ast.Attribute):
                parts.append(cur.attr)
                cur = cur.value
            if isinstance(cur, ast.Name):
                parts.append(cur.id)
            func_name = ".".join(reversed(parts))
        elif isinstance(node.func, ast.Name):
            func_name = node.func.id

        line_no = node.lineno

        # Algorithm-looking text in print/log/user calls is not crypto use.
        selector_calls = {"hashlib.new", "Cipher.getInstance", "MessageDigest.getInstance"}
        for arg in node.args[:1] if func_name in selector_calls else []:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                for pattern, (algo, cat) in _CALL_PATTERNS.items():
                    if pattern in arg.value:
                        evidence = {
                            "call": func_name,
                            "arg": arg.value,
                            "pattern": pattern,
                            "line": line_no,
                        }
                        self.assets.append(
                            CryptoAsset(
                                algorithm=algo,
                                category=cat,
                                source="ast",
                                location=self.filepath,
                                evidence=evidence,
                                confidence=0.90,
                            )
                        )

        # Check function name itself
        for pattern, (algo, cat) in _CALL_PATTERNS.items():
            if pattern in {"sha256", "sha512", "sha1", "md5", "blake2b", "blake2s"}:
                continue
            if pattern in func_name:
                evidence = {
                    "call": func_name,
                    "line": line_no,
                    "match": pattern,
                }
                # Avoid duplicate if already recorded from arg
                if not any(
                    a.evidence.get("line") == line_no and a.algorithm == algo
                    for a in self.assets
                ):
                    self.assets.append(
                        CryptoAsset(
                            algorithm=algo,
                            category=cat,
                            source="ast",
                            location=self.filepath,
                            evidence=evidence,
                            confidence=0.90,
                        )
                    )

        # hashlib.sha256() etc.
        if func_name in ("hashlib.sha256", "hashlib.sha512",
                         "hashlib.sha1", "hashlib.md5", "hashlib.blake2b",
                         "hashlib.blake2s"):
            algo_map = {
                "hashlib.sha256": "SHA-256",
                "hashlib.sha512": "SHA-512",
                "hashlib.sha1": "SHA-1",
                "hashlib.md5": "MD5",
                "hashlib.blake2b": "BLAKE2",
                "hashlib.blake2s": "BLAKE2",
            }
            algo = algo_map.get(func_name, "hash")
            evidence = {"call": func_name, "line": line_no}
            self.assets.append(
                CryptoAsset(
                    algorithm=algo,
                    category="hash",
                    source="ast",
                    location=self.filepath,
                    evidence=evidence,
                    confidence=0.90,
                )
            )

        self.generic_visit(node)


class ASTCollector:
    """AST-based static analysis collector for Python source files."""

    def scan_file(self, path: str, on_error=None) -> list[CryptoAsset]:
        """Parse a Python file and return detected crypto assets."""
        assets: list[CryptoAsset] = []
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                source = fh.read()
            tree = ast.parse(source)
            visitor = _CryptoVisitor(path)
            visitor.visit(tree)
            assets = visitor.assets
        except (SyntaxError, OSError, ValueError, RecursionError):
            if on_error is not None:
                on_error(path)
        return assets

    def scan_directory(self, root: str) -> dict[tuple[str, str], list[dict]]:
        """Scan all .py files under root, return dict keyed by (algorithm, filepath)."""
        results: dict[tuple[str, str], list[dict]] = {}
        for dirpath, _dirnames, filenames in os.walk(root):
            for fname in filenames:
                if not fname.endswith(".py"):
                    continue
                full_path = os.path.join(dirpath, fname)
                file_assets = self.scan_file(full_path)
                for asset in file_assets:
                    key = (asset.algorithm, asset.location)
                    results.setdefault(key, []).append(asset.to_dict())
        return results
