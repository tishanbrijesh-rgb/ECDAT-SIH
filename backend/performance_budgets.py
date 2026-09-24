"""
Performance budget definitions for the ECDAT backend and scanner pipeline.

These constants are the authoritative source for budget limits.  Tests import
from this module so that tightening a budget requires editing only one file.

Budget origins (Phase 8 — September 2026):
    - max_scan_time_per_file_ms:     50 ms   (typical AST+rule scan of a small file)
    - max_memory_per_1000_files_mb:  512 MB  (CI container limit)
    - max_evidence_count_per_file:   50      (cap on correlated findings per file)
"""

from __future__ import annotations

# ── Backend / scanner budgets ───────────────────────────────────────────────

#: Maximum wall-clock time allowed for scanning a single file (milliseconds).
MAX_SCAN_TIME_PER_FILE_MS: int = 50

#: Approximate maximum RSS memory allowed per 1 000 files scanned (megabytes).
MAX_MEMORY_PER_1000_FILES_MB: int = 512

#: Maximum correlated evidence items retained for a single input file.
MAX_EVIDENCE_COUNT_PER_FILE: int = 50


def get_backend_budgets() -> dict[str, int]:
    """Return all backend budget constants as a plain dict (useful for CI)."""
    return {
        "max_scan_time_per_file_ms": MAX_SCAN_TIME_PER_FILE_MS,
        "max_memory_per_1000_files_mb": MAX_MEMORY_PER_1000_FILES_MB,
        "max_evidence_count_per_file": MAX_EVIDENCE_COUNT_PER_FILE,
    }


# ── Frontend bundle budgets ─────────────────────────────────────────────────

#: Maximum total gzipped bundle size (kilobytes).
MAX_BUNDLE_GZIP_KB: int = 500

#: Maximum initial JavaScript bundle size (kilobytes).
MAX_INITIAL_JS_KB: int = 200

#: Maximum total CSS bundle size (kilobytes).
MAX_CSS_KB: int = 50


def get_frontend_budgets() -> dict[str, int]:
    """Return all frontend budget constants as a plain dict."""
    return {
        "max_bundle_gzip_kb": MAX_BUNDLE_GZIP_KB,
        "max_initial_js_kb": MAX_INITIAL_JS_KB,
        "max_css_kb": MAX_CSS_KB,
    }
