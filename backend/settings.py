"""Typed, fail-closed application configuration.

Environment variables are parsed through this module so readiness and request
authentication agree on whether a deployment is usable.  The cached loader is
keyed by the relevant environment values; production processes load one stable
instance while tests can safely exercise isolated environments.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from urllib.parse import urlsplit

ROLES = frozenset({"admin", "security_analyst", "auditor", "viewer"})
_PLACEHOLDER_SECRETS = frozenset(
    {"change-this-secret-before-deployment", "replace-with-a-long-random-secret"}
)
_SETTING_NAMES = (
    "ECDAT_ENV",
    "ECDAT_TOKEN_SECRET",
    "ECDAT_USERS_JSON",
    "ECDAT_CORS_ORIGINS",
    "ECDAT_ALLOWED_SCAN_ROOTS",
    "ECDAT_ALLOW_UNRESTRICTED_SCAN_ROOTS",
    "ECDAT_ALLOW_ROLE_HEADER",
    "ECDAT_REQUEST_TIMEOUT",
    "ECDAT_SCAN_TIMEOUT_SECONDS",
    "ECDAT_MAX_FILE_BYTES",
    "ECDAT_MAX_SCAN_FILES",
    "ECDAT_MAX_EVIDENCE",
    "ECDAT_SCAN_DURATION_BUDGET_MS",
    "ECDAT_SCAN_MEMORY_BUDGET_MB",
    "ECDAT_CORRELATOR_VERSION",
)


class SettingsError(ValueError):
    """Detailed configuration error intended for server logs, not responses."""


@dataclass(frozen=True)
class UserAccount:
    role: str
    password: str


@dataclass(frozen=True)
class Settings:
    environment: str
    token_secret: bytes
    users: Mapping[str, UserAccount]
    cors_origins: tuple[str, ...]
    allowed_scan_roots: tuple[Path, ...]
    allow_unrestricted_scan_roots: bool
    allow_role_header: bool
    request_timeout_seconds: float
    scan_timeout_seconds: int
    max_file_bytes: int
    max_scan_files: int
    max_evidence: int
    scan_duration_budget_ms: int
    scan_memory_budget_mb: int
    correlator_version: str

    @property
    def production(self) -> bool:
        return self.environment == "production"


def _boolean(values: Mapping[str, str], name: str, default: bool = False) -> bool:
    raw = values.get(name, str(default)).strip().lower()
    if raw not in {"true", "false"}:
        raise SettingsError(f"{name} must be true or false")
    return raw == "true"


def _integer(
    values: Mapping[str, str], name: str, default: int, minimum: int, maximum: int
) -> int:
    try:
        value = int(values.get(name, str(default)))
    except (TypeError, ValueError) as exc:
        raise SettingsError(f"{name} must be an integer") from exc
    if value < minimum or value > maximum:
        raise SettingsError(f"{name} must be between {minimum} and {maximum}")
    return value


def _number(
    values: Mapping[str, str], name: str, default: float, minimum: float, maximum: float
) -> float:
    try:
        value = float(values.get(name, str(default)))
    except (TypeError, ValueError) as exc:
        raise SettingsError(f"{name} must be numeric") from exc
    if value < minimum or value > maximum:
        raise SettingsError(f"{name} must be between {minimum:g} and {maximum:g}")
    return value


def _users(values: Mapping[str, str], secret: str) -> Mapping[str, UserAccount]:
    try:
        raw_users = json.loads(values.get("ECDAT_USERS_JSON", ""))
    except json.JSONDecodeError as exc:
        raise SettingsError("ECDAT_USERS_JSON must be valid JSON") from exc
    if not isinstance(raw_users, dict) or not raw_users:
        raise SettingsError("ECDAT_USERS_JSON must contain at least one account")

    accounts: dict[str, UserAccount] = {}
    passwords: list[str] = []
    for username, value in raw_users.items():
        if not isinstance(username, str) or not username or username != username.lower():
            raise SettingsError("ECDAT user names must be non-empty lowercase strings")
        if not isinstance(value, dict):
            raise SettingsError(f"ECDAT user {username!r} must be an object")
        role = value.get("role")
        password = value.get("password")
        if role not in ROLES:
            raise SettingsError(f"ECDAT user {username!r} has an invalid role")
        if not isinstance(password, str) or len(password) < 16:
            raise SettingsError(f"ECDAT user {username!r} has a weak password")
        accounts[username] = UserAccount(role=role, password=password)
        passwords.append(password)
    if len(passwords) != len(set(passwords)):
        raise SettingsError("ECDAT account passwords must be distinct")
    if secret in passwords:
        raise SettingsError("ECDAT_TOKEN_SECRET must differ from account passwords")
    return MappingProxyType(accounts)


def load_settings(values: Mapping[str, str]) -> Settings:
    """Parse and validate a complete settings snapshot."""
    environment = values.get("ECDAT_ENV", "local").strip().lower()
    if environment not in {"local", "test", "production"}:
        raise SettingsError("ECDAT_ENV must be local, test, or production")

    secret = values.get("ECDAT_TOKEN_SECRET", "")
    if len(secret) < 32 or secret in _PLACEHOLDER_SECRETS:
        raise SettingsError("ECDAT_TOKEN_SECRET must be a non-placeholder secret of 32+ characters")
    users = _users(values, secret)

    origins = tuple(
        origin.strip()
        for origin in values.get(
            "ECDAT_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
        ).split(",")
        if origin.strip()
    )
    if not origins:
        raise SettingsError("ECDAT_CORS_ORIGINS must contain at least one origin")
    for origin in origins:
        parsed = urlsplit(origin)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.path not in {"", "/"}:
            raise SettingsError(f"Invalid CORS origin: {origin!r}")
    if environment == "production" and any(origin == "*" for origin in origins):
        raise SettingsError("Wildcard CORS is not allowed in production")

    configured_roots = values.get("ECDAT_ALLOWED_SCAN_ROOTS", "").strip()
    roots = tuple(
        Path(raw.strip()).expanduser().resolve()
        for raw in configured_roots.split(os.pathsep)
        if raw.strip()
    )
    allow_unrestricted = _boolean(values, "ECDAT_ALLOW_UNRESTRICTED_SCAN_ROOTS")
    if roots and allow_unrestricted:
        raise SettingsError("Configure scan roots or unrestricted local scanning, not both")
    if not roots and not allow_unrestricted:
        raise SettingsError("No allowed scan roots are configured")
    if environment == "production" and (not roots or allow_unrestricted):
        raise SettingsError("Production requires non-empty allowed scan roots")
    if environment == "production":
        missing_roots = [str(root) for root in roots if not root.is_dir()]
        if missing_roots:
            raise SettingsError(f"Configured scan roots are not directories: {missing_roots!r}")

    allow_role_header = _boolean(values, "ECDAT_ALLOW_ROLE_HEADER")
    if environment == "production" and allow_role_header:
        raise SettingsError("ECDAT_ALLOW_ROLE_HEADER cannot be enabled in production")

    correlator_version = values.get("ECDAT_CORRELATOR_VERSION", "v2").strip().lower()
    if correlator_version not in {"v2", "v3"}:
        raise SettingsError("ECDAT_CORRELATOR_VERSION must be v2 or v3")

    return Settings(
        environment=environment,
        token_secret=secret.encode(),
        users=users,
        cors_origins=origins,
        allowed_scan_roots=roots,
        allow_unrestricted_scan_roots=allow_unrestricted,
        allow_role_header=allow_role_header,
        request_timeout_seconds=_number(values, "ECDAT_REQUEST_TIMEOUT", 120, 1, 3600),
        scan_timeout_seconds=_integer(values, "ECDAT_SCAN_TIMEOUT_SECONDS", 300, 1, 3600),
        max_file_bytes=_integer(values, "ECDAT_MAX_FILE_BYTES", 8 * 1024 * 1024, 1, 128 * 1024 * 1024),
        max_scan_files=_integer(values, "ECDAT_MAX_SCAN_FILES", 100_000, 1, 1_000_000),
        max_evidence=_integer(values, "ECDAT_MAX_EVIDENCE", 100_000, 1, 1_000_000),
        scan_duration_budget_ms=_integer(values, "ECDAT_SCAN_DURATION_BUDGET_MS", 0, 0, 3_600_000),
        scan_memory_budget_mb=_integer(values, "ECDAT_SCAN_MEMORY_BUDGET_MB", 512, 0, 4096),
        correlator_version=correlator_version,
    )


@lru_cache(maxsize=8)
def _settings_from_snapshot(snapshot: tuple[tuple[str, str], ...]) -> Settings:
    return load_settings(dict(snapshot))


def get_settings() -> Settings:
    """Return a cached settings object for the current process environment."""
    snapshot = tuple((name, os.environ[name]) for name in _SETTING_NAMES if name in os.environ)
    return _settings_from_snapshot(snapshot)


def clear_settings_cache() -> None:
    """Clear cached snapshots for isolated tests."""
    _settings_from_snapshot.cache_clear()
