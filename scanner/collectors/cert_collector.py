"""
Certificate collector — parses PEM-encoded X.509 certificates using
the `cryptography` library, extracting algorithm, key size, subject, issuer,
and expiry information.
"""

from __future__ import annotations

import os
import re
import warnings

from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import dsa, ec, ed25519, rsa
from cryptography.utils import CryptographyDeprecationWarning
from cryptography.x509.oid import NameOID

from scanner.limits import read_bytes
from scanner.models.asset import CryptoAsset


def _split_pem_blocks(data: str) -> list[str]:
    """Split a concatenated PEM file into individual certificate blocks."""
    pattern = re.compile(
        r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----",
        re.DOTALL,
    )
    return pattern.findall(data)


def _parse_pem_block(pem_bytes: bytes) -> x509.Certificate | None:
    """Load one X.509 block, treating deprecations as controlled failures."""
    try:
        with warnings.catch_warnings():
            # Some currently accepted certificates (for example, those with a
            # non-positive serial number) are scheduled to become hard errors.
            # Handle them consistently now instead of changing scan behavior on
            # a future cryptography upgrade.
            warnings.simplefilter("error", CryptographyDeprecationWarning)
            return x509.load_pem_x509_certificate(pem_bytes)
    except Exception:
        return None


def _common_name(name: x509.Name) -> str:
    """Return a printable common name without leaking malformed-name errors."""
    try:
        return str(name.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value)
    except CryptographyDeprecationWarning:
        raise
    except Exception:
        return ""


def _eku_to_usage(eku_oids: list[str]) -> str:
    """Map Extended Key Usage OIDs to a usage label."""
    eku_lower = [o.lower() for o in eku_oids]
    if any("serverauth" in o for o in eku_lower) or any("1.3.6.1.5.5.7.3.1" in o for o in eku_lower):
        return "tls"
    if any("clientauth" in o for o in eku_lower) or any("1.3.6.1.5.5.7.3.2" in o for o in eku_lower):
        return "tls"
    if any("codesigning" in o for o in eku_lower) or any("1.3.6.1.5.5.7.3.3" in o for o in eku_lower):
        return "signature"
    if any("emailprotection" in o for o in eku_lower):
        return "signature"
    return "unknown"


def _extract_eku(cert: x509.Certificate) -> tuple[list[str], str]:
    """Extract EKU OIDs and derive usage from certificate extensions."""
    try:
        eku_ext = cert.extensions.get_extension_for_oid(
            x509.oid.ExtensionOID.EXTENDED_KEY_USAGE
        )
        oids = [str(o.dotted_string) for o in eku_ext.value]  # type: ignore[attr-defined]
        return oids, _eku_to_usage(oids)
    except Exception:
        return [], "unknown"


def _asset_from_certificate(cert: x509.Certificate, path: str) -> CryptoAsset:
    """Convert a validated certificate to evidence; callers contain failures."""
    pub_key = cert.public_key()
    try:
        key_size = pub_key.key_size  # type: ignore[union-attr]
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

    not_after = cert.not_valid_after_utc.isoformat() if cert.not_valid_after_utc else ""
    signature_hash = cert.signature_hash_algorithm
    eku_oids, eku_usage = _extract_eku(cert)

    # Phase 2: usage defaults to "unknown" unless EKU establishes a role.
    usage = eku_usage
    if usage != "unknown":
        evidence_kind = "configured_protocol"
    else:
        evidence_kind = "artifact_metadata"
        usage = "unknown"

    evidence = {
        "key_size": key_size,
        "subject_cn": _common_name(cert.subject),
        "issuer": _common_name(cert.issuer),
        "version": cert.version.name,
        "not_after": not_after,
        "validity_not_before": cert.not_valid_before_utc.isoformat()
        if cert.not_valid_before_utc else "",
        "serial_number": str(cert.serial_number),
        "signature_hash_algorithm": signature_hash.name if signature_hash else "unknown",
        "signature_algorithm": cert.signature_algorithm_oid._name
        if hasattr(cert.signature_algorithm_oid, "_name") else str(cert.signature_algorithm_oid),
        "eku_oids": eku_oids,
        "chain_position": None,
    }

    # Optional extensions extracted via try/except
    try:
        ku_ext = cert.extensions.get_extension_for_oid(
            x509.oid.ExtensionOID.KEY_USAGE
        )
        ku = ku_ext.value
        key_usage_flags = []
        if ku.digital_signature:  # type: ignore[attr-defined]
            key_usage_flags.append("digitalSignature")
        if ku.key_encipherment:  # type: ignore[attr-defined]
            key_usage_flags.append("keyEncipherment")
        if ku.key_agreement:  # type: ignore[attr-defined]
            key_usage_flags.append("keyAgreement")
        if ku.key_cert_sign:  # type: ignore[attr-defined]
            key_usage_flags.append("keyCertSign")
        if ku.crl_sign:  # type: ignore[attr-defined]
            key_usage_flags.append("cRLSign")
        evidence["key_usage"] = key_usage_flags
    except Exception:
        evidence["key_usage"] = []

    try:
        bc_ext = cert.extensions.get_extension_for_oid(
            x509.oid.ExtensionOID.BASIC_CONSTRAINTS
        )
        evidence["is_ca"] = bc_ext.value.ca  # type: ignore[attr-defined]
    except Exception:
        evidence["is_ca"] = False

    try:
        san_ext = cert.extensions.get_extension_for_oid(
            x509.oid.ExtensionOID.SUBJECT_ALTERNATIVE_NAME
        )
        san_names = []
        for name in san_ext.value:  # type: ignore[attr-defined]
            san_names.append(name.value)
        evidence["san"] = san_names
    except Exception:
        evidence["san"] = []

    evidence["usage"] = usage

    confidence_reasons = [
        {"source": "cert", "evidence_kind": evidence_kind,
         "base": 0.95, "bonus": 0.0, "penalty": 0.0,
         "note": f"artifact metadata; EKU {'established' if eku_usage != 'unknown' else 'not established'}"}
    ]

    return CryptoAsset(
        algorithm=algorithm,
        category=category,
        source="cert",
        location=path,
        evidence=evidence,
        confidence=0.95,
        evidence_kind=evidence_kind,
        parser_version="cert-v2",
        span={"file": path, "line_start": None,
              "line_end": None, "column_start": None,
              "column_end": None},
        confidence_reasons=confidence_reasons,
    )


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

            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("error", CryptographyDeprecationWarning)
                    assets.append(_asset_from_certificate(cert, path))
            except Exception:
                if on_error is not None:
                    on_error(path)
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
