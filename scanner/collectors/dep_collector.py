"""
Dependency collector — parses requirements.txt and pom.xml to detect
crypto libraries that may not be directly visible in source code.
"""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any

from scanner.models.asset import CryptoAsset
from scanner.limits import read_text
from scanner.rules.crypto_patterns import get_category


# Map known crypto packages to algorithms they typically provide
_REQ_ALGO_MAP: dict[str, list[tuple[str, str]]] = {
    "cryptography": [("RSA", "encryption"), ("AES", "encryption"),
                     ("ECDSA", "signature"), ("Ed25519", "signature"),
                     ("SHA-256", "hash")],
    "pycryptodome": [("AES", "encryption"), ("RSA", "encryption"),
                     ("ECDSA", "signature"), ("SHA-256", "hash")],
    "pycryptodomex": [("AES", "encryption"), ("RSA", "encryption"),
                      ("ECDSA", "signature"), ("SHA-256", "hash")],
    "pyopenssl": [("TLS", "protocol")],
    "ecdsa": [("ECDSA", "signature")],
    "pyjwt": [("RSA", "encryption"), ("HMAC", "hash")],
    "pyotp": [("HMAC", "hash"), ("SHA-1", "hash")],
    "pynacl": [("Ed25519", "signature"), ("ChaCha20", "encryption")],
    "paramiko": [("RSA", "encryption"), ("ECDSA", "signature"), ("AES", "encryption")],
    "bcrypt": [("bcrypt", "hash")],
    "scrypt": [("scrypt", "hash")],
    "argon2-cffi": [("Argon2", "hash")],
    "pysha3": [("SHA-3", "hash"), ("SHAKE", "hash")],
    "pyblake2": [("BLAKE2", "hash")],
    "python-jose": [("RSA", "encryption"), ("ECDSA", "signature")],
}

# Java / Maven artifacts -> algorithms
_POM_ALGO_MAP: dict[str, list[tuple[str, str]]] = {
    "org.bouncycastle": [("RSA", "encryption"), ("AES", "encryption"),
                         ("ECDSA", "signature"), ("Ed25519", "signature"),
                         ("SHA-256", "hash"), ("ML-DSA", "signature"),
                         ("ML-KEM", "key_exchange")],
    "org.springframework.security": [("RSA", "encryption"), ("ECDSA", "signature")],
    "javax.crypto": [("AES", "encryption"), ("RSA", "encryption"), ("DES", "encryption")],
    "java.security": [("SHA-256", "hash"), ("SHA-1", "hash"), ("MD5", "hash")],
}


def _normalise_pkg_name(raw: str) -> str:
    """Extract a declared package name, without evaluating target environments."""
    pkg = raw.strip().lower()
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
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            pkg = _normalise_pkg_name(line)
            if pkg in _REQ_ALGO_MAP and pkg not in seen:
                seen.add(pkg)
                for algo, cat in _REQ_ALGO_MAP[pkg]:
                    evidence = {
                        "manifest": path,
                        "package": pkg,
                        "raw_line": line,
                    }
                    assets.append(
                        CryptoAsset(
                            algorithm=algo,
                            category=cat,
                            source="dep",
                            location=path,
                            evidence=evidence,
                            confidence=0.70,
                        )
                    )
        return assets

    def scan_pom_xml(self, path: str, on_error=None) -> list[CryptoAsset]:
        """Parse a pom.xml and return crypto assets found."""
        assets: list[CryptoAsset] = []
        if not os.path.isfile(path):
            if on_error is not None:
                on_error(path)
            return assets
        try:
            content = read_text(path)
        except (OSError, UnicodeError):
            if on_error is not None:
                on_error(path)
            return assets

        # Pair coordinates structurally; comments, parents and plugins are not
        # application dependencies. Do not resolve POMs or fetch anything.
        if "<!DOCTYPE" in content.upper() or "<!ENTITY" in content.upper():
            if on_error is not None:
                on_error(path)
            return assets
        try:
            root = ET.fromstring(content)
        except ET.ParseError:
            if on_error is not None:
                on_error(path)
            return assets
        namespace = root.tag.split("}")[0] + "}" if root.tag.startswith("{") else ""
        group_to_artifacts: dict[str, list[str]] = {}
        for dependency in root.findall(f"{namespace}dependencies/{namespace}dependency"):
            group = (dependency.findtext(f"{namespace}groupId") or "").strip()
            artifact = (dependency.findtext(f"{namespace}artifactId") or "").strip()
            if group and artifact:
                group_to_artifacts.setdefault(group, []).append(artifact)

        seen: set[str] = set()
        for group_id, artifacts in group_to_artifacts.items():
            norm_group = group_id.strip().lower()
            for map_group, algo_list in _POM_ALGO_MAP.items():
                if map_group == norm_group:
                    for artifact in artifacts:
                        key = f"{norm_group}:{artifact}"
                        if key not in seen:
                            seen.add(key)
                            for algo, cat in algo_list:
                                assets.append(
                                    CryptoAsset(
                                        algorithm=algo,
                                        category=cat,
                                        source="dep",
                                        location=path,
                                        evidence={
                                            "manifest": path,
                                            "groupId": group_id,
                                            "artifactId": artifact,
                                        },
                                        confidence=0.70,
                                    )
                                )
        return assets

    def scan_directory(self, root: str) -> dict[tuple[str, str], list[dict]]:
        """Walk root and scan all dependency manifests."""
        results: dict[tuple[str, str], list[dict]] = {}
        for dirpath, _dirs, filenames in os.walk(root):
            for fname in filenames:
                full_path = os.path.join(dirpath, fname)
                file_assets: list[CryptoAsset] = []
                if fname == "requirements.txt":
                    file_assets = self.scan_requirements(full_path)
                elif fname == "pom.xml":
                    file_assets = self.scan_pom_xml(full_path)
                for asset in file_assets:
                    key = (asset.algorithm, asset.location)
                    results.setdefault(key, []).append(asset.to_dict())
        return results
