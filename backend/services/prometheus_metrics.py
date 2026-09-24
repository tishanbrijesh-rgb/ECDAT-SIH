"""Pure-stdlib Prometheus text exposition format — no third-party dependencies.

Exposes:
- ecdat_total_requests (counter by method, path, status)
- ecdat_request_duration_seconds_sum (gauge by method, path, status)
- ecdat_scan_jobs_total (counter)
- ecdat_scan_duration_seconds_{p50|p95|p99} (gauges)
- ecdat_active_scans (gauge)
- ecdat_scan_duration_samples (gauge)
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict

from backend.services.scan_metrics import scan_metrics

# ── Request metrics store ──────────────────────────────────────────────────────
# Maps (method, path_template, status_code) -> count / total_duration_s
# path_template should be the literal path (no template expansion).
_req_counts: dict[tuple[str, str, str], int] = defaultdict(int)
_req_duration_sums: dict[tuple[str, str, str], float] = defaultdict(float)
_req_lock = threading.Lock()

# Number of currently active scans (set by the scan supervisor / control module).
_active_scans: int = 0
_active_scans_lock = threading.Lock()


def inc_request(method: str, path: str, status_code: int) -> None:
    """Increment the request counter for a given (method, path, status)."""
    key = (method.upper(), _normalise_path(path), str(status_code))
    with _req_lock:
        _req_counts[key] += 1


def observe_request_duration(method: str, path: str, status_code: int, duration_s: float) -> None:
    """Accumulate request duration for a given (method, path, status)."""
    key = (method.upper(), _normalise_path(path), str(status_code))
    with _req_lock:
        _req_duration_sums[key] += duration_s


def set_active_scans(count: int) -> None:
    """Set the active-scans gauge."""
    global _active_scans
    with _active_scans_lock:
        _active_scans = count


# ── Scan job metric helpers ────────────────────────────────────────────────────

# (status_label) -> total count
_scan_job_counts: dict[str, int] = defaultdict(int)
_scan_lock = threading.Lock()


def inc_scan_job(status: str) -> None:
    """Increment the scan-job counter for the given terminal status."""
    with _scan_lock:
        _scan_job_counts[status] += 1


def observe_scan_duration(status: str, duration_s: float) -> None:
    """Accumulate duration for a scan job of the given status.

    This is recorded into the request-duration sums under a synthetic key so it
    appears in the same _ecdat_scan_duration_seconds_sum_ metric family when
    a proper histogram is desired later.  For now it feeds the exposition
    directly alongside request-level sums.
    """
    # Reuse the request-duration store under a synthetic "scan" method key.
    key = ("SCAN", status, "ok")
    with _req_lock:
        _req_duration_sums[key] += duration_s


# ── Path normalisation ─────────────────────────────────────────────────────────
_PATH_NORMALISATIONS: list[tuple[str, str]] = [
    ("/scans/", "/scans/{id}"),
    ("/scans/{id}/events", "/scans/{id}/events"),
    ("/scans/{id}/cancel", "/scans/{id}/cancel"),
    ("/assets/", "/assets/{id}"),
    ("/dashboard/summary", "/dashboard/summary"),
    ("/metrics", "/metrics"),
    ("/api/admin/metrics", "/api/admin/metrics"),
]


def _normalise_path(path: str) -> str:
    """Reduce parameterised paths to a stable template so label cardinality stays low."""
    # Exact match first.
    for raw, tpl in _PATH_NORMALISATIONS:
        if path == raw or path.startswith(raw) and raw.endswith("/"):
            return tpl
    return path


# ── Renderer ──────────────────────────────────────────────────────────────────


def render_prometheus() -> str:
    """Return the full Prometheus text exposition format."""
    lines: list[str] = []
    now_ms = int(time.time() * 1000)

    with _req_lock:
        counts_snapshot = dict(_req_counts)
        sums_snapshot = dict(_req_duration_sums)

    with _active_scans_lock:
        active = _active_scans

    ranks = scan_metrics.percentile_ranks()

    # ── ecdat_total_requests ────────────────────────────────────────────────────
    lines.append("# HELP ecdat_total_requests Total HTTP requests received.")
    lines.append("# TYPE ecdat_total_requests counter")
    for (method, path, status), count in sorted(counts_snapshot.items()):
        labels = f'method="{method}",path="{path}",status="{status}"'
        lines.append(f'ecdat_total_requests{{{labels}}} {count} {now_ms}')
    lines.append("")

    # ── ecdat_request_duration_seconds_sum ─────────────────────────────────────
    lines.append("# HELP ecdat_request_duration_seconds_sum Cumulative request duration by method/path/status.")
    lines.append("# TYPE ecdat_request_duration_seconds_sum gauge")
    for (method, path, status), total_s in sorted(sums_snapshot.items()):
        labels = f'method="{method}",path="{path}",status="{status}"'
        lines.append(f'ecdat_request_duration_seconds_sum{{{labels}}} {total_s:.6f} {now_ms}')
    lines.append("")

    # ── ecdat_scan_jobs_total ───────────────────────────────────────────────────
    lines.append("# HELP ecdat_scan_jobs_total Total scan jobs by terminal status since process start.")
    lines.append("# TYPE ecdat_scan_jobs_total counter")
    lines.append(f"ecdat_scan_jobs_total {scan_metrics.total_scans} {now_ms}")
    with _scan_lock:
        for status, count in sorted(_scan_job_counts.items()):
            lines.append(f'ecdat_scan_jobs_total{{status="{status}"}} {count} {now_ms}')
    lines.append("")

    # ── ecdat_active_scans ──────────────────────────────────────────────────────
    lines.append("# HELP ecdat_active_scans Number of scans currently running.")
    lines.append("# TYPE ecdat_active_scans gauge")
    lines.append(f"ecdat_active_scans {active} {now_ms}")
    lines.append("")

    # ── ecdat_scan_duration_seconds_{p50|p95|p99} ───────────────────────────────
    def _emit_gauge(name: str, help_text: str, ms_val: float | None) -> None:
        lines.append(f"# HELP {name} {help_text}")
        lines.append(f"# TYPE {name} gauge")
        val_s = _ms_to_s(ms_val)
        lines.append(f"{name} {val_s:.6f} {now_ms}")
        lines.append("")

    _emit_gauge(
        "ecdat_scan_duration_seconds_p50",
        "p50 scan duration in seconds over last 100 scans.",
        ranks.get("p50"),
    )
    _emit_gauge(
        "ecdat_scan_duration_seconds_p95",
        "p95 scan duration in seconds over last 100 scans.",
        ranks.get("p95"),
    )
    _emit_gauge(
        "ecdat_scan_duration_seconds_p99",
        "p99 scan duration in seconds over last 100 scans.",
        ranks.get("p99"),
    )

    # ── ecdat_scan_duration_samples ────────────────────────────────────────────
    lines.append("# HELP ecdat_scan_duration_samples Number of samples in the rolling percentile window.")
    lines.append("# TYPE ecdat_scan_duration_samples gauge")
    lines.append(f"ecdat_scan_duration_samples {ranks.get('sample_count', 0)} {now_ms}")
    lines.append("")

    return "\n".join(lines)


def _ms_to_s(ms: float | None) -> float:
    if ms is None:
        return 0.0
    return round(ms / 1000.0, 6)
