"""
Scanner layer models — CryptoAsset dataclass represents a discovered
cryptographic asset with its evidence chain, confidence, and metadata.

Phase 2: evidence_kind taxonomy distinguishes how each finding was produced:
  observed_operation  – runtime or call-site use confirmed in source
  declared_capability – library imported or dependency declared, no confirmed operation
  configured_protocol – protocol configured but role unproven (e.g. cert without EKU)
  artifact_metadata   – metadata about an artifact with no usage claim
  unknown             – cannot determine the kind
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

EVIDENCE_KINDS = (
    "observed_operation",
    "declared_capability",
    "configured_protocol",
    "artifact_metadata",
    "unknown",
)


@dataclass
class CryptoAsset:
    """A cryptographic asset discovered during scanning."""
    asset_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    algorithm: str = ""
    category: str = ""  # encryption | signature | hash | key_exchange | mac | protocol
    source: str = ""  # ast | dep | cert | semgrep | binary | rule
    location: str = ""  # file path or identifier
    evidence: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    evidence_kind: str = "unknown"
    parser_version: str = ""
    span: dict[str, Any] | None = None
    confidence_reasons: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["evidence"] = self.evidence
        return d
