"""Rebuild split corpus manifests from the declarative combined manifest."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

OUTPUT_DIR = Path(__file__).with_name("manifests")
TEMPLATE_PATH = OUTPUT_DIR / "all.json"


def _load_entries() -> list[dict[str, Any]]:
    payload = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))
    entries = payload.get("entries")
    if not isinstance(entries, list) or payload.get("total_entries") != len(entries):
        raise ValueError("all.json must contain a consistent declarative corpus")
    return entries


def build_manifests() -> dict[str, dict[str, Any]]:
    """Return every manifest exactly as it should appear on disk."""
    entries = _load_entries()
    languages = sorted({str(item["language"]) for item in entries})
    manifests = {
        f"{language}.json": {
            "language": language,
            "entries": [item for item in entries if item["language"] == language],
        }
        for language in languages
    }
    manifests["all.json"] = {"total_entries": len(entries), "entries": entries}
    return manifests


def _validate(entries: list[dict[str, Any]]) -> None:
    polarity = Counter(bool(item["positive"]) for item in entries)
    families = Counter(str(item["algorithm_family"]) for item in entries)
    assert polarity[True] >= 150, f"Need >=150 positive, got {polarity[True]}"
    assert polarity[False] >= 150, f"Need >=150 negative, got {polarity[False]}"
    assert len(families) == 9, f"Need 9 families, got {len(families)}"
    assert min(families.values()) >= 20, "Every family needs at least 20 entries"


def _serialized(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2)


def regenerate(*, check: bool = False) -> bool:
    """Write manifests, or return whether committed files are current."""
    manifests = build_manifests()
    _validate(manifests["all.json"]["entries"])
    drifted: list[str] = []
    for name, payload in manifests.items():
        path = OUTPUT_DIR / name
        expected = _serialized(payload)
        if check:
            if not path.exists() or path.read_text(encoding="utf-8") != expected:
                drifted.append(name)
        else:
            path.write_text(expected, encoding="utf-8")
    if drifted:
        print("Corpus drift detected: " + ", ".join(drifted))
    return not drifted


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if manifests drifted")
    args = parser.parse_args()
    return 0 if regenerate(check=args.check) else 1


if __name__ == "__main__":
    raise SystemExit(main())
