"""Corpus generator reproducibility contract."""

import json
from pathlib import Path

from scanner.corpus.generate_manifests import build_manifests


def test_build_manifests_matches_committed_outputs() -> None:
    manifest_dir = Path(__file__).parents[1] / "scanner" / "corpus" / "manifests"
    generated = build_manifests()

    assert generated
    for name, payload in generated.items():
        committed = json.loads((manifest_dir / name).read_text(encoding="utf-8"))
        assert payload == committed, f"generated corpus drifted: {name}"
