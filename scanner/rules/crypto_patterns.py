"""
Crypto pattern rules — regex patterns and categories used by the
scanner as a fallback when AST parsing isn't available, and as a
reference for labeling detected algorithms.
"""
import json
import os

# Resolve path relative to this file
_RULES_DIR = os.path.dirname(os.path.abspath(__file__))
_JSON_PATH = os.path.join(_RULES_DIR, "crypto_patterns.json")

# In-memory cache of loaded rules
_RULES_CACHE: dict | None = None


def load_rules() -> dict:
    """Load and return the crypto pattern rules from JSON."""
    global _RULES_CACHE
    if _RULES_CACHE is None:
        with open(_JSON_PATH, "r", encoding="utf-8") as fh:
            _RULES_CACHE = json.load(fh)
    return _RULES_CACHE


def get_algorithm_patterns(algorithm: str) -> list[str]:
    """Return regex patterns for a given algorithm name."""
    rules = load_rules()
    entry = rules.get("algorithms", {}).get(algorithm)
    if entry is None:
        return []
    return entry.get("patterns", [])


def get_category(algorithm: str) -> str:
    """Return the category for a given algorithm."""
    rules = load_rules()
    entry = rules.get("algorithms", {}).get(algorithm)
    if entry is None:
        return "unknown"
    return entry.get("category", "unknown")
