"""Focused regressions for safe X.509 certificate collection."""

from __future__ import annotations

import tempfile
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch

from cryptography import x509
from cryptography.utils import CryptographyDeprecationWarning

from scanner.collectors.cert_collector import CertCollector


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VALID_CERTIFICATE = PROJECT_ROOT / "test-repo" / "certs" / "server.crt"


class _InvalidCertificate:
    """Certificate-shaped object that models future lazy validation failures."""

    def public_key(self):
        raise ValueError("sensitive parser detail must not escape")


class CertificateCollectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pem = VALID_CERTIFICATE.read_bytes()
        cls.certificate = x509.load_pem_x509_certificate(cls.pem)

    def test_deprecation_warning_marks_only_affected_bundle_block_failed(self) -> None:
        calls = 0

        def load_with_first_block_warning(_pem_bytes):
            nonlocal calls
            calls += 1
            if calls == 1:
                warnings.warn(
                    "non-positive serial numbers will be rejected",
                    CryptographyDeprecationWarning,
                )
            return self.certificate

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bundle.pem"
            path.write_bytes(self.pem + b"\n" + self.pem)
            failures: list[str] = []
            with patch(
                "scanner.collectors.cert_collector.x509.load_pem_x509_certificate",
                side_effect=load_with_first_block_warning,
            ):
                with warnings.catch_warnings(record=True) as emitted:
                    warnings.simplefilter("always")
                    assets = CertCollector().scan_cert(str(path), on_error=failures.append)

        self.assertEqual(len(assets), 1)
        self.assertEqual(failures, [str(path)])
        self.assertFalse(emitted)

    def test_metadata_failure_is_sanitized_and_next_bundle_block_continues(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bundle.pem"
            path.write_bytes(self.pem + b"\n" + self.pem)
            failures: list[str] = []
            with patch(
                "scanner.collectors.cert_collector.x509.load_pem_x509_certificate",
                side_effect=[_InvalidCertificate(), self.certificate],
            ):
                assets = CertCollector().scan_cert(str(path), on_error=failures.append)

        self.assertEqual(len(assets), 1)
        self.assertEqual(failures, [str(path)])
        self.assertEqual(assets[0].algorithm, "RSA")


if __name__ == "__main__":
    unittest.main()
