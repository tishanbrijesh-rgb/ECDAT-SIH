"""
Dependency collector — parses requirements.txt, pom.xml, and lockfiles to detect
crypto libraries that may not be directly visible in source code.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any

from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException

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

# npm / Node packages -> algorithms
_NPM_ALGO_MAP: dict[str, list[tuple[str, str]]] = {
    "crypto-js": [("AES", "encryption"), ("DES", "encryption"),
                  ("SHA-256", "hash"), ("SHA-1", "hash"), ("HMAC", "hash")],
    "bcryptjs": [("bcrypt", "hash")],
    "node-forge": [("RSA", "encryption"), ("ECDSA", "signature"),
                   ("SHA-256", "hash"), ("TLS", "protocol")],
    "jose": [("RSA", "encryption"), ("ECDSA", "signature"), ("Ed25519", "signature")],
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
}

# Rust crates -> algorithms
_RUST_ALGO_MAP: dict[str, list[tuple[str, str]]] = {
    "ring": [("AES", "encryption"), ("SHA-256", "hash"), ("ECDSA", "signature")],
    "rustls": [("TLS", "protocol")],
    "ed25519-dalek": [("Ed25519", "signature")],
    "bincode": [],
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
        except (ET.ParseError, DefusedXmlException):
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

    def scan_package_lock(self, path: str, on_error=None) -> list[CryptoAsset]:
        """Parse a package-lock.json and return crypto assets found."""
        assets: list[CryptoAsset] = []
        if not os.path.isfile(path):
            if on_error is not None:
                on_error(path)
            return assets
        try:
            content = read_text(path)
            data = __import__("json").loads(content)
        except (OSError, UnicodeError, ValueError):
            if on_error is not None:
                on_error(path)
            return assets
        lockfile_version = data.get("lockfileVersion", "")
        packages: dict[str, dict] = data.get("packages", {}) or {}
        dependencies: dict[str, dict] = data.get("dependencies", {}) or {}
        seen: set[str] = set()
        pkg_map: dict[str, dict] = {}
        if packages:
            for name, info in packages.items():
                if not name or name == "":
                    continue
                pkg_map[name] = info
        if dependencies:
            for name, info in dependencies.items():
                pkg_map.setdefault(name, info)
        for name, info in pkg_map.items():
            pkg = _normalise_pkg_name(name)
            if pkg in _NPM_ALGO_MAP and pkg not in seen:
                seen.add(pkg)
                version = info.get("version", "") if isinstance(info, dict) else ""
                for algo, cat in _NPM_ALGO_MAP[pkg]:
                    assets.append(
                        CryptoAsset(
                            algorithm=algo, category=cat, source="dep", location=path,
                            evidence={"manifest": path, "package": pkg, "version": version,
                                      "lockfile_version": str(lockfile_version)},
                            confidence=0.70,
                        )
                    )
        return assets

    def scan_gemfile_lock(self, path: str, on_error=None) -> list[CryptoAsset]:
        """Parse a Gemfile.lock and return crypto assets found."""
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
        seen: set[str] = set()
        current_spec: dict[str, str] = {}
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith(("  ", "\t")) and "(" in stripped and ")" in stripped:
                pkg_match = re.match(r'^\s*([A-Za-z0-9_.\-]+)\s*\(', stripped)
                if pkg_match:
                    pkg = _normalise_pkg_name(pkg_match.group(1))
                    current_spec[pkg] = stripped
            elif stripped and not stripped.startswith((" ", "\t")) and not stripped.startswith("#"):
                current_spec = {}
                pkg = _normalise_pkg_name(stripped)
                if pkg in _GEM_ALGO_MAP and pkg not in seen:
                    seen.add(pkg)
                    for algo, cat in _GEM_ALGO_MAP[pkg]:
                        assets.append(
                            CryptoAsset(
                                algorithm=algo, category=cat, source="dep", location=path,
                                evidence={"manifest": path, "package": pkg, "spec": current_spec.get(pkg, "")},
                                confidence=0.70,
                            )
                        )
        return assets

    def scan_go_sum(self, path: str, on_error=None) -> list[CryptoAsset]:
        """Parse a go.sum and return crypto assets found."""
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
        seen: set[str] = set()
        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) >= 2:
                mod_path = parts[0].strip()
                pkg = _normalise_pkg_name(mod_path.split("/")[-1])
                if pkg in _GO_ALGO_MAP and pkg not in seen:
                    seen.add(pkg)
                    for algo, cat in _GO_ALGO_MAP[pkg]:
                        assets.append(
                            CryptoAsset(
                                algorithm=algo, category=cat, source="dep", location=path,
                                evidence={"manifest": path, "package": mod_path},
                                confidence=0.70,
                            )
                        )
        return assets

    def scan_cargo_lock(self, path: str, on_error=None) -> list[CryptoAsset]:
        """Parse a Cargo.lock and return crypto assets found."""
        assets: list[CryptoAsset] = []
        if not os.path.isfile(path):
            if on_error is not None:
                on_error(path)
            return assets
        try:
            content = read_text(path)
            data = __import__("tomllib").loads(content)
        except (OSError, UnicodeError, ValueError, Exception):
            if on_error is not None:
                on_error(path)
            return assets
        package_section = data.get("package", [])
        if isinstance(package_section, dict):
            package_section = package_section.get("package", [])
        seen: set[str] = set()
        for entry in package_section:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name", "")
            pkg = _normalise_pkg_name(name)
            if pkg in _RUST_ALGO_MAP and pkg not in seen:
                seen.add(pkg)
                version = entry.get("version", "")
                for algo, cat in _RUST_ALGO_MAP[pkg]:
                    assets.append(
                        CryptoAsset(
                            algorithm=algo, category=cat, source="dep", location=path,
                            evidence={"manifest": path, "package": pkg, "version": version},
                            confidence=0.70,
                        )
                    )
        return assets

    def scan_directory(self, root: str) -> dict[tuple[str, str], list[dict]]:
        """Walk root and scan all dependency manifests and lockfiles."""
        results: dict[tuple[str, str], list[dict]] = {}
        for dirpath, _dirs, filenames in os.walk(root):
            for fname in filenames:
                full_path = os.path.join(dirpath, fname)
                file_assets: list[CryptoAsset] = []
                if fname == "requirements.txt":
                    file_assets = self.scan_requirements(full_path)
                elif fname == "pom.xml":
                    file_assets = self.scan_pom_xml(full_path)
                elif fname == "package-lock.json":
                    file_assets = self.scan_package_lock(full_path)
                elif fname == "Gemfile.lock":
                    file_assets = self.scan_gemfile_lock(full_path)
                elif fname == "go.sum":
                    file_assets = self.scan_go_sum(full_path)
                elif fname == "Cargo.lock":
                    file_assets = self.scan_cargo_lock(full_path)
                for asset in file_assets:
                    key = (asset.algorithm, asset.location)
                    results.setdefault(key, []).append(asset.to_dict())
        return results
