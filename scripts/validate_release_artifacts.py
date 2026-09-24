"""Validate and optionally stamp benchmark artifacts with build provenance."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
from typing import Any


def validate_artifact(kind: str, path: Path, *, stamp: bool = False) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("artifact must be a JSON object")
    if stamp:
        payload["provenance"] = {
            "git_sha": os.getenv("GITHUB_SHA", "local"),
            "workflow_run_id": os.getenv("GITHUB_RUN_ID", "local"),
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        }
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    if not isinstance(payload.get("provenance"), dict):
        raise ValueError("artifact provenance is missing")
    if kind == "corpus":
        precision = (payload.get("overall") or {}).get("micro_precision")
        if not isinstance(precision, (int, float)):
            raise ValueError("corpus artifact is missing overall.micro_precision")
    elif kind == "calibration":
        for key in ("version", "brier_score", "ece", "sample_count"):
            if key not in payload:
                raise ValueError(f"calibration artifact is missing {key}")
    else:
        raise ValueError(f"unsupported artifact kind: {kind}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("corpus", "calibration"))
    parser.add_argument("path", type=Path)
    parser.add_argument("--stamp", action="store_true")
    args = parser.parse_args()
    validate_artifact(args.kind, args.path, stamp=args.stamp)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
