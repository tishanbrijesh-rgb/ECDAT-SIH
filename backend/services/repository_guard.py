"""Repository path resolution and optional deployment boundary enforcement."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import HTTPException


def resolve_repository(raw_path: str) -> str:
    if raw_path == "/test-repo" and not Path(raw_path).is_dir():
        raw_path = str(Path(__file__).resolve().parents[2] / "test-repo")
    try:
        candidate = Path(raw_path).expanduser().resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise HTTPException(400, f"Repository path does not exist: {raw_path}") from exc
    if not candidate.is_dir():
        raise HTTPException(400, f"Repository path is not a directory: {raw_path}")

    configured = os.getenv("ECDAT_ALLOWED_SCAN_ROOTS", "").strip()
    if configured:
        roots = [Path(value).expanduser().resolve() for value in configured.split(os.pathsep) if value.strip()]
        if not any(candidate == root or candidate.is_relative_to(root) for root in roots):
            raise HTTPException(403, "Repository is outside the configured scan roots")
    return str(candidate)
