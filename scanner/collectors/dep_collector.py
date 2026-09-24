"""
Dependency collector — parses requirements.txt, pom.xml, and lockfiles to detect
crypto libraries that may not be directly visible in source code.
"""

from __future__ import annotations

import os
import re

from scanner.collectors.dependency_formats import (
    cargo_packages,
    gem_packages,
    go_packages,
    npm_packages,
    pom_packages,
)
from scanner.limits import read_text
from scanner.models.asset import CryptoAsset

# Map known crypto packages to algorithms they typically provide
_REQ_ALGO_MAP: dict[str, list[tuple[str, str]]] = {
    "cryptography": [("RSA", "encryption"), ("AES", "encryption"),
                     ("ECDSA", "signature"), ("Ed25519", "signature"),
                     ("SHA-256", "hash"), ("ChaCha20", "encryption")],
    "cryptography-fernet": [("AES", "encryption"), ("HMAC", "mac")],
    "pycryptodome": [("AES", "encryption"), ("RSA", "encryption"),
                     ("ECDSA", "signature"), ("SHA-256", "hash")],
    "pycryptodomex": [("AES", "encryption"), ("RSA", "encryption"),
                      ("ECDSA", "signature"), ("SHA-256", "hash")],
    "pyopenssl": [("TLS", "protocol")],
    "ecdsa": [("ECDSA", "signature")],
    "pyjwt": [("RSA", "encryption"), ("HMAC", "hash")],
    "pyotp": [("HMAC", "hash"), ("SHA-1", "hash")],
    "pynacl": [("Ed25519", "signature"), ("ChaCha20", "encryption")],
    "pysodium": [("NaCl", "encryption"), ("ChaCha20", "encryption")],
    "paramiko": [("RSA", "encryption"), ("ECDSA", "signature"), ("AES", "encryption")],
    "bcrypt": [("bcrypt", "hash")],
    "scrypt": [("scrypt", "hash")],
    "argon2-cffi": [("Argon2", "hash")],
    "pysha3": [("SHA-3", "hash"), ("SHAKE", "hash")],
    "pyblake2": [("BLAKE2", "hash")],
    "python-jose": [("RSA", "encryption"), ("ECDSA", "signature")],
    "libsodium": [("NaCl", "encryption"), ("ChaCha20", "encryption")],
    "pkcs11": [("RSA", "encryption"), ("ECDSA", "signature"), ("AES", "encryption")],
    "pyhanko": [("RSA", "signature"), ("ECDSA", "signature")],
}

# Java / Maven artifacts -> algorithms
_POM_ALGO_MAP: dict[str, list[tuple[str, str]]] = {
    "org.bouncycastle": [("RSA", "encryption"), ("AES", "encryption"),
                         ("ECDSA", "signature"), ("Ed25519", "signature"),
                         ("SHA-256", "hash"), ("ChaCha20", "encryption"),
                         ("ML-DSA", "signature"), ("ML-KEM", "key_exchange")],
    "org.springframework.security": [("RSA", "encryption"), ("ECDSA", "signature")],
    "javax.crypto": [("AES", "encryption"), ("RSA", "encryption"), ("DES", "encryption")],
    "java.security": [("SHA-256", "hash"), ("SHA-1", "hash"), ("MD5", "hash")],
}

# npm / Node packages -> algorithms
_NPM_ALGO_MAP: dict[str, list[tuple[str, str]]] = {
    "crypto-js": [("AES", "encryption"), ("DES", "encryption"),
                  ("SHA-256", "hash"), ("SHA-1", "hash"), ("HMAC", "hash")],
    "bcryptjs": [("bcrypt", "hash")],
    "node-forge": [("RSA", "encryption"), ("ECDSA", "signature"),
                   ("SHA-256", "hash"), ("TLS", "protocol")],
    "jose": [("RSA", "encryption"), ("ECDSA", "signature"), ("Ed25519", "signature")],
    "tweetnacl": [("ChaCha20", "encryption")],
    "jsrsasign": [("RSA", "encryption"), ("ECDSA", "signature"),
                  ("SHA-256", "hash"), ("HMAC", "hash")],
    "elliptic": [("ECDSA", "signature")],
}

# Ruby Gems -> algorithms
_GEM_ALGO_MAP: dict[str, list[tuple[str, str]]] = {
    "bcrypt": [("bcrypt", "hash")],
    "openssl": [("RSA", "encryption"), ("ECDSA", "signature"), ("AES", "encryption")],
    "rbnacl": [("Ed25519", "signature"), ("ChaCha20", "encryption")],
}

# Go modules -> algorithms
_GO_ALGO_MAP: dict[str, list[tuple[str, str]]] = {
    "golang.org/x/crypto": [("SHA-256", "hash"), ("ECDSA", "signature"),
                            ("Ed25519", "signature"), ("ChaCha20", "encryption")],
    "github.com/golang-jwt/jwt": [("RSA", "encryption"), ("HMAC", "hash")],
    "filippo.io/ed25519": [("Ed25519", "signature")],
    "google/tink/go": [("AES", "encryption"), ("AES-GCM", "encryption"), ("HMAC", "mac")],
}

# Rust crates -> algorithms
_RUST_ALGO_MAP: dict[str, list[tuple[str, str]]] = {
    "ring": [("AES", "encryption"), ("SHA-256", "hash"), ("ECDSA", "signature"),
             ("ChaCha20", "encryption")],
    "rustls": [("TLS", "protocol")],
    "ed25519-dalek": [("Ed25519", "signature")],
    "bincode": [],
    "aes-gcm": [("AES", "encryption")],
    "chacha20poly1305": [("ChaCha20", "encryption")],
    "sha2": [("SHA-256", "hash"), ("SHA-512", "hash")],
    "p256": [("ECDSA", "signature")],
    "p384": [("ECDSA", "signature")],
    "p521": [("ECDSA", "signature")],
    "k256": [("ECDSA", "signature")],
}

# Map internal category labels to the usage field expected by CryptoAsset
_CAT_TO_USAGE: dict[str, str] = {
    "encryption": "encryption",
    "signature": "signature",
    "hash": "hashing",
    "mac": "unknown",
    "protocol": "protocol",
    "key_exchange": "key_exchange",
}


def _cat_to_usage(cat: str) -> str:
    return _CAT_TO_USAGE.get(cat, cat)


_STANDARD_EVIDENCE_KIND = "declared_capability"
_STANDARD_PARSER_VERSION = "dep-v1"
_STANDARD_CONFIDENCE_REASONS = [
    {"source": "dep", "evidence_kind": "declared_capability",
     "base": 0.70, "bonus": 0.0, "penalty": 0.0,
     "note": "dependency declared; operation not confirmed"}
]


def _normalise_pkg_name(raw: str) -> str:
    """Extract a declared package name, without evaluating target environments."""
    pkg = raw.strip().lower()
    # For path-qualified names (e.g. "node_modules/crypto-js"), take the
    # last segment so the registry lookup sees the actual package name.
    if "/" in pkg:
        pkg = pkg.split("/")[-1]
    pkg = re.split(r'[<>=!~\[;@#\s]', pkg)[0]
    pkg = pkg.strip()
    return re.sub(r"[-_.]+", "-", pkg)


class DepCollector:
    """Scans dependency manifests for cryptographic libraries."""

    def scan_requirements(self, path: str, on_error=None) -> list[CryptoAsset]:
        """Parse a requirements.txt and return crypto assets found."""
        assets: list[CryptoAsset] = []
        if not os.path.isfile(path):
            if on_error is not None:
                on_error(path)
            return assets
        try:
            lines = read_text(path).splitlines()
        except (OSError, UnicodeError):
            if on_error is not None:
                on_error(path)
            return assets

        seen: set[str] = set()
        for raw_line in lines:
            line = raw_line.strip()
            if not line or line.startswith(("#", "-")):
                continue
            pkg = _normalise_pkg_name(line)
            if pkg in _REQ_ALGO_MAP and pkg not in seen:
                seen.add(pkg)
                for algo, cat in _REQ_ALGO_MAP[pkg]:
                    evidence = {
                        "manifest": path,
                        "package": pkg,
                        "raw_line": line,
                        "usage": _cat_to_usage(cat),
                    }
                    assets.append(
                        CryptoAsset(
                            algorithm=algo,
                            category=cat,
                            source="dep",
                            location=path,
                            evidence=evidence,
                            confidence=0.70,
                            evidence_kind=_STANDARD_EVIDENCE_KIND,
                            parser_version=_STANDARD_PARSER_VERSION,
                            span={"file": path, "line_start": None,
                                  "line_end": None, "column_start": None,
                                  "column_end": None},
                            confidence_reasons=_STANDARD_CONFIDENCE_REASONS,
                        )
                    )
        return assets

    def scan_pom_xml(self, path: str, on_error=None) -> list[CryptoAsset]:
        """Parse a pom.xml and return crypto assets found."""
        if not os.path.isfile(path):
            if on_error is not None:
                on_error(path)
            return []
        try:
            packages = pom_packages(read_text(path))
        except (OSError, UnicodeError, ValueError):
            if on_error is not None:
                on_error(path)
            return []
        assets: list[CryptoAsset] = []
        seen: set[str] = set()
        for group, key, metadata in packages:
            if group not in _POM_ALGO_MAP or key in seen:
                continue
            seen.add(key)
            for algo, cat in _POM_ALGO_MAP[group]:
                evidence = {"manifest": path, **metadata, "usage": _cat_to_usage(cat)}
                assets.append(self._dependency_asset(path, algo, cat, evidence))
        return assets

    @staticmethod
    def _dependency_asset(path: str, algo: str, cat: str, evidence: dict) -> CryptoAsset:
        return CryptoAsset(
            algorithm=algo,
            category=cat,
            source="dep",
            location=path,
            evidence=evidence,
            confidence=0.70,
            evidence_kind=_STANDARD_EVIDENCE_KIND,
            parser_version=_STANDARD_PARSER_VERSION,
            span={"file": path, "line_start": None, "line_end": None,
                  "column_start": None, "column_end": None},
            confidence_reasons=_STANDARD_CONFIDENCE_REASONS,
        )

    def scan_package_lock(self, path: str, on_error=None) -> list[CryptoAsset]:
        """Parse a package-lock.json and return crypto assets found."""
        if not os.path.isfile(path):
            if on_error is not None:
                on_error(path)
            return []
        try:
            packages = npm_packages(read_text(path))
        except (OSError, UnicodeError, ValueError):
            if on_error is not None:
                on_error(path)
            return []
        assets: list[CryptoAsset] = []
        seen: set[str] = set()
        for package, metadata in packages:
            if package not in _NPM_ALGO_MAP or package in seen:
                continue
            seen.add(package)
            for algo, cat in _NPM_ALGO_MAP[package]:
                evidence = {"manifest": path, **metadata, "usage": _cat_to_usage(cat)}
                assets.append(self._dependency_asset(path, algo, cat, evidence))
        return assets

    def scan_gemfile_lock(self, path: str, on_error=None) -> list[CryptoAsset]:
        """Parse a Gemfile.lock and return crypto assets found."""
        if not os.path.isfile(path):
            if on_error is not None:
                on_error(path)
            return []
        try:
            packages = gem_packages(read_text(path))
        except (OSError, UnicodeError):
            if on_error is not None:
                on_error(path)
            return []
        assets: list[CryptoAsset] = []
        seen: set[str] = set()
        for package, metadata in packages:
            if package not in _GEM_ALGO_MAP or package in seen:
                continue
            seen.add(package)
            for algo, cat in _GEM_ALGO_MAP[package]:
                evidence = {"manifest": path, **metadata, "usage": _cat_to_usage(cat)}
                assets.append(self._dependency_asset(path, algo, cat, evidence))
        return assets

    def scan_go_sum(self, path: str, on_error=None) -> list[CryptoAsset]:
        """Parse a go.sum and return crypto assets found."""
        if not os.path.isfile(path):
            if on_error is not None:
                on_error(path)
            return []
        try:
            packages = go_packages(read_text(path))
        except (OSError, UnicodeError):
            if on_error is not None:
                on_error(path)
            return []
        assets: list[CryptoAsset] = []
        seen: set[str] = set()
        for package, metadata in packages:
            key = package if package in _GO_ALGO_MAP else _normalise_pkg_name(package.split("/")[-1])
            if key not in _GO_ALGO_MAP or key in seen:
                continue
            seen.add(key)
            for algo, cat in _GO_ALGO_MAP[key]:
                evidence = {"manifest": path, **metadata, "usage": _cat_to_usage(cat)}
                assets.append(self._dependency_asset(path, algo, cat, evidence))
        return assets

    def scan_cargo_lock(self, path: str, on_error=None) -> list[CryptoAsset]:
        """Parse a Cargo.lock and return crypto assets found."""
        if not os.path.isfile(path):
            if on_error is not None:
                on_error(path)
            return []
        try:
            packages = cargo_packages(read_text(path))
        except (OSError, UnicodeError, ValueError):
            if on_error is not None:
                on_error(path)
            return []
        assets: list[CryptoAsset] = []
        seen: set[str] = set()
        for package, metadata in packages:
            key = _normalise_pkg_name(package)
            if key not in _RUST_ALGO_MAP or key in seen:
                continue
            seen.add(key)
            for algo, cat in _RUST_ALGO_MAP[key]:
                evidence = {"manifest": path, **metadata, "usage": _cat_to_usage(cat)}
                assets.append(self._dependency_asset(path, algo, cat, evidence))
        return assets

    def scan_directory(self, root: str) -> dict[tuple[str, str], list[dict]]:
        """Walk root and scan all dependency manifests and lockfiles."""
        from scanner.collectors.registry import CollectorRegistry
        registry = CollectorRegistry()
        results: dict[tuple[str, str], list[dict]] = {}
        for dirpath, _dirs, filenames in os.walk(root):
            for fname in filenames:
                full_path = os.path.join(dirpath, fname)
                file_assets: list[CryptoAsset] = []
                for name, handler in registry.handlers_for(full_path):
                    if name == "dep":
                        file_assets = handler(full_path)
                for asset in file_assets:
                    key = (asset.algorithm, asset.location)
                    results.setdefault(key, []).append(asset.to_dict())
        return results
