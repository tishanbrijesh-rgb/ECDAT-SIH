"""Regression tests for centralized deployment settings and readiness."""

from __future__ import annotations

import json
import secrets
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from fastapi import HTTPException

from backend.settings import (
    SettingsError,
    clear_settings_cache,
    get_settings,
    load_settings,
)


def _valid_environment() -> dict[str, str]:
    return {
        "ECDAT_ENV": "production",
        "ECDAT_TOKEN_SECRET": secrets.token_urlsafe(48),
        "ECDAT_USERS_JSON": json.dumps(
            {
                "analyst": {
                    "role": "security_analyst",
                    "password": secrets.token_urlsafe(24),
                }
            }
        ),
        "ECDAT_CORS_ORIGINS": "https://ecdat.example",
        "ECDAT_SCAN_TIMEOUT_SECONDS": "300",
        "ECDAT_REQUEST_TIMEOUT": "120",
        "ECDAT_MAX_FILE_BYTES": "8388608",
        "ECDAT_MAX_SCAN_FILES": "100000",
        "ECDAT_MAX_EVIDENCE": "100000",
        "ECDAT_CORRELATOR_VERSION": "v2",
    }


class ReadinessConfigurationTests(TestCase):
    def test_production_without_scan_roots_fails_with_generic_detail(self) -> None:
        from backend.main import readiness

        environment = _valid_environment()
        environment["ECDAT_ALLOWED_SCAN_ROOTS"] = ""
        with patch.dict("os.environ", environment, clear=True):
            with self.assertRaises(HTTPException) as error:
                readiness()

        self.assertEqual(503, error.exception.status_code)
        self.assertEqual("Service configuration is invalid", error.exception.detail)


class SettingsValidationTests(TestCase):
    def valid_environment(self) -> dict[str, str]:
        environment = _valid_environment()
        environment["ECDAT_ALLOWED_SCAN_ROOTS"] = str(Path.cwd())
        return environment

    def test_invalid_auth_json_is_rejected(self) -> None:
        environment = self.valid_environment()
        environment["ECDAT_USERS_JSON"] = "{not-json"
        with self.assertRaisesRegex(SettingsError, "valid JSON"):
            load_settings(environment)

    def test_weak_token_secret_is_rejected(self) -> None:
        environment = self.valid_environment()
        environment["ECDAT_TOKEN_SECRET"] = "too-short"
        with self.assertRaisesRegex(SettingsError, r"32\+"):
            load_settings(environment)

    def test_unknown_user_role_is_rejected(self) -> None:
        environment = self.valid_environment()
        environment["ECDAT_USERS_JSON"] = json.dumps(
            {"analyst": {"role": "owner", "password": secrets.token_urlsafe(24)}}
        )
        with self.assertRaisesRegex(SettingsError, "invalid role"):
            load_settings(environment)

    def test_invalid_numeric_limit_is_rejected(self) -> None:
        environment = self.valid_environment()
        environment["ECDAT_MAX_EVIDENCE"] = "unbounded"
        with self.assertRaisesRegex(SettingsError, "must be an integer"):
            load_settings(environment)

    def test_all_bounded_numeric_settings_reject_invalid_values(self) -> None:
        invalid_values = {
            "ECDAT_REQUEST_TIMEOUT": "0",
            "ECDAT_SCAN_TIMEOUT_SECONDS": "3601",
            "ECDAT_MAX_FILE_BYTES": "0",
            "ECDAT_MAX_SCAN_FILES": "1000001",
            "ECDAT_SCAN_DURATION_BUDGET_MS": "-1",
            "ECDAT_SCAN_MEMORY_BUDGET_MB": "4097",
        }
        for name, value in invalid_values.items():
            with self.subTest(name=name):
                environment = self.valid_environment()
                environment[name] = value
                with self.assertRaises(SettingsError):
                    load_settings(environment)

    def test_invalid_cors_origin_is_rejected(self) -> None:
        environment = self.valid_environment()
        environment["ECDAT_CORS_ORIGINS"] = "javascript:alert(1)"
        with self.assertRaisesRegex(SettingsError, "Invalid CORS origin"):
            load_settings(environment)

    def test_unknown_correlator_version_is_rejected(self) -> None:
        environment = self.valid_environment()
        environment["ECDAT_CORRELATOR_VERSION"] = "experimental"
        with self.assertRaisesRegex(SettingsError, "must be v2 or v3"):
            load_settings(environment)

    def test_local_unrestricted_scanning_requires_explicit_opt_in(self) -> None:
        environment = self.valid_environment()
        environment["ECDAT_ENV"] = "local"
        environment["ECDAT_ALLOWED_SCAN_ROOTS"] = ""
        with self.assertRaisesRegex(SettingsError, "No allowed scan roots"):
            load_settings(environment)

        environment["ECDAT_ALLOW_UNRESTRICTED_SCAN_ROOTS"] = "true"
        settings = load_settings(environment)
        self.assertTrue(settings.allow_unrestricted_scan_roots)
        self.assertEqual((), settings.allowed_scan_roots)

    def test_current_environment_snapshot_is_cached(self) -> None:
        environment = self.valid_environment()
        clear_settings_cache()
        with patch.dict("os.environ", environment, clear=True):
            self.assertIs(get_settings(), get_settings())
        clear_settings_cache()
