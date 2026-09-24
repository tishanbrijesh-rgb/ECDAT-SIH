"""In-memory scan duration percentile tracking for admin observability."""
from __future__ import annotations

import logging
import threading
from collections.abc import Sequence

_logger = logging.getLogger("ecdat.scan_metrics")


class ScanMetrics:
    """Tracks scan durations in a fixed-size ring buffer and computes percentiles.

    Thread-safe — uses a lock around buffer mutations.
    """

    def __init__(self, capacity: int = 100) -> None:
        self._capacity = capacity
        self._buffer: list[float] = []
        self._lock = threading.Lock()
        self._total_scans = 0

    def record(self, duration_ms: float) -> None:
        """Record a completed scan's wall-clock duration in milliseconds."""
        if duration_ms < 0:
            return
        with self._lock:
            self._buffer.append(duration_ms)
            self._total_scans += 1
            if len(self._buffer) > self._capacity:
                self._buffer = self._buffer[-self._capacity:]
        _logger.debug("Scan duration recorded", extra={"extra_data": {"duration_ms": duration_ms}})

    def percentile(self, p: float, sorted_vals: Sequence[float] | None = None) -> float | None:
        """Return the *p*-th percentile (0–100) of recorded durations in ms.

        Returns ``None`` when no samples exist.
        """
        with self._lock:
            vals = sorted_vals if sorted_vals is not None else list(self._buffer)
        if not vals:
            return None
        k = (len(vals) - 1) * (p / 100.0)
        f = int(k)
        c = min(f + 1, len(vals) - 1)
        d = k - f
        return vals[f] + d * (vals[c] - vals[f])

    def percentile_ranks(self) -> dict[str, float | None]:
        """Return p50, p95, p99 for the current buffer."""
        with self._lock:
            if not self._buffer:
                return {"p50": None, "p95": None, "p99": None, "sample_count": 0}
            sorted_vals = sorted(self._buffer)
        return {
            "p50": self.percentile(50, sorted_vals),
            "p95": self.percentile(95, sorted_vals),
            "p99": self.percentile(99, sorted_vals),
            "sample_count": len(self._buffer),
        }

    @property
    def total_scans(self) -> int:
        """Total scans recorded since process start (includes evicted samples)."""
        return self._total_scans

    @property
    def sample_count(self) -> int:
        """Current number of samples held in the ring buffer."""
        return len(self._buffer)


# Global singleton — accessed by the admin endpoint and the scan supervisor.
scan_metrics = ScanMetrics(capacity=100)
