"""Release artifact provenance and schema checks."""

import json

import pytest

from scripts.validate_release_artifacts import validate_artifact


def test_corpus_artifact_requires_precision_and_provenance(tmp_path) -> None:
    path = tmp_path / "results.json"
    path.write_text(json.dumps({"overall": {"micro_precision": 0.9}}), encoding="utf-8")

    with pytest.raises(ValueError, match="provenance"):
        validate_artifact("corpus", path)
