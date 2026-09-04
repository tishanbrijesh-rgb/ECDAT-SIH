"""
Scanner layer models — CryptoAsset dataclass represents a discovered
cryptographic asset with its evidence chain, confidence, and metadata.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class CryptoAsset:
    """A cryptographic asset discovered during scanning."""
    asset_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    algorithm: str = ""
    category: str = ""  # encryption | signature | hash | key_exchange
    source: str = ""  # ast | dep | cert | semgrep | binary
    location: str = ""  # file path or identifier
    evidence: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["evidence"] = self.evidence
        return d
