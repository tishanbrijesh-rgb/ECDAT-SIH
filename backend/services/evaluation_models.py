"""Typed internal contracts for evaluation operations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EvaluatedOperation:
    original_algorithm: str
    algorithm: str
    component: str
    usage: str = "unknown"
    key_size: int | None = None
    line: int | None = None
    file: str = ""
    confidence: float = 1.0
    _matched: bool = False
    _pair_index: int = -1
