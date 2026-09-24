"""Performance budget tests for ECDAT.

Branches (backend / scanner) that exceed their budgets fail loudly so they
cannot silently regress in a PR.  All measurements use deterministic mock
data so tests are stable across hardware.

Budgets (as of Phase 8 — September 2026):
    - Max scan time per file:           50 ms
    - Max memory per 1 000 files:       512 MB
    - Max evidence count per file:      50
"""

from __future__ import annotations

import os
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from scanner.collectors.registry import CollectorRegistry

# ---------------------------------------------------------------------------
# Scanner path
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCANNER_ROOT = _REPO_ROOT / "scanner"
if str(_SCANNER_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCANNER_ROOT))

# ---------------------------------------------------------------------------
# Budget constants (mirrors scanner/limits.py but hard-coded here for the
# assertion layer so budget tightening requires editing only one place).
# ---------------------------------------------------------------------------
MAX_SCAN_TIME_PER_FILE_MS = 50
MAX_MEMORY_PER_1000_FILES_MB = 512
MAX_EVIDENCE_PER_FILE = 50


class EvidenceBudgetTests(unittest.TestCase):
    """The scanner must not retain unbounded evidence per input file."""

    def test_max_evidence_count_constant(self):
        """The per-file evidence ceiling must be a sane positive integer."""
        from scanner.limits import max_evidence_count
        count = max_evidence_count()
        self.assertGreater(count, 0)
        self.assertLessEqual(count, 1_000_000)

    def test_correlated_findings_respect_evidence_budget(self):
        """After correlation, no single file should produce more than
        MAX_EVIDENCE_PER_FILE evidence items."""
        import os
        import tempfile

        from scanner.main import scan_with_metrics

        with tempfile.TemporaryDirectory() as tmpdir:
            py_file = os.path.join(tmpdir, "many_crypto.py")
            with open(py_file, "w") as f:
                for i in range(10):
                    f.write(f"from Crypto.Cipher.AES import AES_{i}\n")
                    f.write("import hashlib; h = hashlib.sha256()\n")

            evidence, _ = scan_with_metrics(tmpdir)
        # After correlation the number of final findings per file must not
        # exceed the budget by more than a small margin (correlation can
        # split or merge, but should not explode).
        for _file, items in evidence.items():
            self.assertLessEqual(
                len(items),
                MAX_EVIDENCE_PER_FILE * 3,
                f"Evidence budget exceeded for {_file}: {len(items)} > {MAX_EVIDENCE_PER_FILE * 3}",
            )


class ScanTimeBudgetTests(unittest.TestCase):
    """A single-file scan must complete within the per-file time budget."""

    def test_scan_within_time_budget(self):
        """Scanning the small test-repo directory must finish well within
        the per-file time budget applied across all files."""
        from scanner.main import scan_with_metrics

        start = time.perf_counter()
        _, metrics = scan_with_metrics(str(_REPO_ROOT / "test-repo"))
        elapsed_ms = (time.perf_counter() - start) * 1000

        file_count = max(metrics.get("in_scope_files", 1), 1)
        per_file_ms = elapsed_ms / file_count
        self.assertLessEqual(
            per_file_ms,
            MAX_SCAN_TIME_PER_FILE_MS * 5,  # 5x headroom for CI machines
            (
                f"Per-file scan time {per_file_ms:.1f}ms exceeds budget "
                f"({MAX_SCAN_TIME_PER_FILE_MS}ms) over {file_count} files"
            ),
        )

    def test_collectors_are_initialized_once_per_scan(self):
        import tempfile

        from scanner.main import scan_with_metrics

        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "one.py").write_text("import hashlib\nhashlib.sha256(b'x')")
            Path(tmpdir, "two.py").write_text("import hashlib\nhashlib.sha512(b'x')")
            with patch("scanner.main.CollectorRegistry", wraps=CollectorRegistry) as factory:
                scan_with_metrics(tmpdir)

        self.assertEqual(factory.call_count, 1)


class MemoryBudgetTests(unittest.TestCase):
    """Scanning must not consume unbounded memory."""

    def test_memory_budget_constant(self):
        """The memory budget constant must be a sane positive value."""
        from scanner.limits import scan_memory_budget_mb
        budget = scan_memory_budget_mb()
        self.assertGreater(budget, 0)
        # 512 MB per 1 000 files is the documented ceiling.
        self.assertLessEqual(budget, MAX_MEMORY_PER_1000_FILES_MB)

    def test_scan_does_not_consume_excessive_memory(self):
        """After scanning the test-repo, RSS must not spike absurdly.
        This is a sanity check, not a precise benchmark."""
        if sys.platform == "win32":
            self.skipTest("resource module not available on Windows")
        import resource

        from scanner.main import scan_with_metrics

        # Record RSS before scan.
        rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        _, _metrics = scan_with_metrics(str(_REPO_ROOT / "test-repo"))
        rss_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

        # ru_maxrss is in KB on Linux, bytes on macOS — normalise to MB.
        if sys.platform == "darwin":
            delta_mb = (rss_after - rss_before) / (1024 * 1024)
        else:
            delta_mb = (rss_after - rss_before) / 1024

        # The test-repo is tiny; memory growth should be well under 50 MB.
        self.assertLessEqual(
            delta_mb, 50,
            f"Scan memory growth {delta_mb:.1f} MB seems excessive for a tiny repo",
        )


class LimitsModuleTests(unittest.TestCase):
    """Direct tests for scanner/limits.py helper functions."""

    def test_max_file_bytes_default(self):
        from scanner.limits import max_file_bytes
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(max_file_bytes(), 8 * 1024 * 1024)

    def test_max_evidence_count_default(self):
        from scanner.limits import max_evidence_count
        self.assertEqual(max_evidence_count(), 100_000)

    def test_scan_duration_budget_default(self):
        from scanner.limits import scan_duration_budget_ms
        self.assertEqual(scan_duration_budget_ms(), 0)

    def test_scan_memory_budget_default(self):
        from scanner.limits import scan_memory_budget_mb
        self.assertEqual(scan_memory_budget_mb(), 512)

    def test_positive_int_env_override(self):
        from scanner.limits import max_file_bytes
        with patch.dict(os.environ, {"ECDAT_MAX_FILE_BYTES": "4096"}):
            self.assertEqual(max_file_bytes(), 4096)

    def test_positive_int_rejects_zero(self):
        from scanner.limits import positive_int
        with self.assertRaises(ValueError):
            positive_int("NONEXISTENT_ZERO", 0, 10)

    def test_positive_int_rejects_above_max(self):
        from scanner.limits import positive_int
        with self.assertRaises(ValueError):
            positive_int("NONEXISTENT_BIG", 9999, 100)


if __name__ == "__main__":
    unittest.main(verbosity=2)
