"""
Certificate collector — parses PEM-encoded X.509 certificates using
the `cryptography` library, extracting algorithm, key size, subject, issuer,
and expiry information.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import dsa, ec, ed25519, rsa
from cryptography.x509.oid import NameOID
from scanner.models.asset import CryptoAsset
from scanner.limits import read_bytes


def _split_pem_blocks(data: str) -> list[str]:
    """Split a concatenated PEM file into individual certificate blocks."""
    pattern = re.compile(
        r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----",
        re.DOTALL,
    )
    return pattern.findall(data)


def _parse_pem_block(pem_bytes: bytes) -> x509.Certificate | None:
    """Try to load a single PEM block as an X.509 certificate."""
    for label in ("CERTIFICATE", "X509 CERTIFICATE"):
        try:
            return x509.load_pem_x509_certificate(pem_bytes, default_backend())
        except Exception:
            pass
    return None


class CertCollector:
    """Scans .crt / .pem files and extracts crypto metadata."""

    def scan_cert(self, path: str, on_error=None) -> list[CryptoAsset]:
        """Parse a single PEM certificate file and return crypto assets."""
        assets: list[CryptoAsset] = []
        try:
            data = read_bytes(path)
        except OSError:
            if on_error is not None:
                on_error(path)
            return assets

        blocks = _split_pem_blocks(data.decode("utf-8", errors="replace"))
        if not blocks:
            if on_error is not None:
                on_error(path)
            return assets

        for block in blocks:
            cert = _parse_pem_block(block.encode("utf-8"))
            if cert is None:
                if on_error is not None:
                    on_error(path)
                continue

            # --- Algorithm & key size ---
            pub_key = cert.public_key()
            try:
                key_size = pub_key.key_size
            except (AttributeError, TypeError):
                key_size = 0

            algo_name = type(pub_key).__name__
            if isinstance(pub_key, rsa.RSAPublicKey):
                algorithm = "RSA"
                category = "encryption"
            elif isinstance(pub_key, ec.EllipticCurvePublicKey):
                algorithm = "ECDSA"
                category = "signature"
            elif isinstance(pub_key, ed25519.Ed25519PublicKey):
                algorithm = "Ed25519"
                category = "signature"
            elif isinstance(pub_key, dsa.DSAPublicKey):
                algorithm = "DSA"
                category = "signature"
            else:
                algorithm = algo_name
                category = "unknown"

            # --- Subject CN ---
            subject_cn = ""
            try:
                subject_cn = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
            except (IndexError, Exception):
                pass

            # --- Issuer ---
            issuer_cn = ""
            try:
                issuer_cn = cert.issuer.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
            except (IndexError, Exception):
                pass

            # --- Expiry ---
            not_after = cert.not_valid_after_utc.isoformat() if cert.not_valid_after_utc else ""

            evidence = {
                "key_size": key_size,
                "subject_cn": str(subject_cn),
                "issuer": str(issuer_cn),
                "not_after": not_after,
                "serial_number": str(cert.serial_number),
                "signature_hash_algorithm": cert.signature_hash_algorithm.name
                if cert.signature_hash_algorithm else "unknown",
            }

            assets.append(
                CryptoAsset(
                    algorithm=algorithm,
                    category=category,
                    source="cert",
                    location=path,
                    evidence=evidence,
                    confidence=0.95,
                )
            )
        return assets

    def scan_directory(self, root: str) -> dict[tuple[str, str], list[dict]]:
        """Walk root and scan all .crt/.pem/.cer files."""
        results: dict[tuple[str, str], list[dict]] = {}
        for dirpath, _dirs, filenames in os.walk(root):
            for fname in filenames:
                if not fname.lower().endswith((".crt", ".pem", ".cer")):
                    continue
                full_path = os.path.join(dirpath, fname)
                file_assets = self.scan_cert(full_path)
                for asset in file_assets:
                    key = (asset.algorithm, asset.location)
                    results.setdefault(key, []).append(asset.to_dict())
        return results
