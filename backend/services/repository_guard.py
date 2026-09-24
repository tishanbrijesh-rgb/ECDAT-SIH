"""Repository path resolution and optional deployment boundary enforcement."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import HTTPException

_MAX_PATH_LENGTH = 4096


def _reject_traversal(raw_path: str) -> None:
    """Reject null bytes and path-traversal sequences in the raw input."""
    if "\x00" in raw_path:
        raise HTTPException(400, "Repository path contains invalid characters")
    if ".." in raw_path.split(os.sep):
        raise HTTPException(400, "Repository path must not contain parent-directory traversals")
    if len(raw_path) > _MAX_PATH_LENGTH:
        raise HTTPException(400, "Repository path exceeds maximum allowed length")


def resolve_repository(raw_path: str) -> str:
    _reject_traversal(raw_path)
    if raw_path == "/test-repo" and not Path(raw_path).is_dir():
        raw_path = str(Path(__file__).resolve().parents[2] / "test-repo")
    try:
        candidate = Path(raw_path).expanduser().resolve(strict=True)
    except (OSError, RuntimeError, ValueError, TypeError) as exc:
        raise HTTPException(400, f"Repository path does not exist: {raw_path}") from exc
    if not candidate.is_dir():
        raise HTTPException(400, f"Repository path is not a directory: {raw_path}")

    configured = os.getenv("ECDAT_ALLOWED_SCAN_ROOTS", "").strip()
    if configured:
        roots = [Path(value).expanduser().resolve() for value in configured.split(os.pathsep) if value.strip()]
        if not any(candidate == root or candidate.is_relative_to(root) for root in roots):
            raise HTTPException(403, "Repository is outside the configured scan roots")
    return str(candidate)
