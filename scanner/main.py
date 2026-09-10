#!/usr/bin/env python3
"""
Scanner entrypoint — orchestrates all collectors, walks a repository, and
returns a structured evidence map suitable for ingestion by the correlator.

Usage:
    from scanner.main import scan
    evidence = scan("/path/to/repo")
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any, Callable
from urllib.parse import quote

from scanner.collectors.ast_collector import ASTCollector
from scanner.collectors.dep_collector import DepCollector
from scanner.collectors.cert_collector import CertCollector
from scanner.collectors.rule_collector import CODE_EXTENSIONS, RuleCollector
from scanner.redaction import redact_evidence
from scanner.limits import positive_int, max_evidence_count, max_file_bytes, scan_duration_budget_ms, scan_memory_budget_mb, check_memory_budget

# Ensure `scanner` package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging as _logging
_scanner_logger = _logging.getLogger("ecdat.scanner")


def _print(msg: str) -> None:
    """Log progress message via structured logger."""
    _scanner_logger.info(msg)


def _safe_filename(repo_path: str) -> str:
    """Display-friendly repo path."""
    return os.path.basename(repo_path.rstrip("/\\")) or repo_path


def _scan_profile() -> str:
    """Return the declared inventory profile, failing closed on typos."""
    profile = os.getenv("ECDAT_SCAN_PROFILE", "source").strip().lower()
    if profile not in {"source", "environment"}:
        raise ValueError("Invalid ECDAT_SCAN_PROFILE")
    return profile


def _inventory(repo_path: str, profile: str | None = None) -> tuple[list[str], list[str], dict[str, str]]:
    """Return all files, supported files, and fixed failure codes by path."""
    all_files: list[str] = []
    supported: list[str] = []
    failed: dict[str, str] = {}
    file_limit = positive_int('ECDAT_MAX_SCAN_FILES', 100000, 1000000)
    byte_limit = max_file_bytes()
    excluded = {
        ".git", "node_modules", "dist", "build", "__pycache__",
        ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox", ".nox", ".runtime",
    }
    if (profile or _scan_profile()) == "source":
        excluded.update({".venv", "venv", "env"})

    def inventory_error(_error: OSError) -> None:
        # Do not leak inaccessible absolute paths or platform error details.
        raise OSError("Unable to inventory repository tree") from None

    for dirpath, dirnames, filenames in os.walk(repo_path, onerror=inventory_error):
        dirnames[:] = [d for d in dirnames if d not in excluded
                      and not os.path.islink(os.path.join(dirpath, d))
                      and not getattr(os.path, 'isjunction', lambda p: False)(os.path.join(dirpath, d))]
        for filename in filenames:
            path = os.path.join(dirpath, filename)
            all_files.append(path)
            if len(all_files) > file_limit:
                raise ValueError('Repository exceeds configured file count limit')
            ext = os.path.splitext(filename)[1].lower()
            if ext in CODE_EXTENSIONS or filename in {"requirements.txt", "pom.xml"} or ext in {".crt", ".pem", ".cer"}:
                supported.append(path)
                try:
                    if os.path.islink(path):
                        failed[path] = "linked_file"
                        continue
                    if os.path.getsize(path) > byte_limit:
                        failed[path] = "oversized"
                        continue
                    with open(path, "rb") as stream:
                        stream.read(1)
                except OSError:
                    failed[path] = "unreadable"
    return all_files, supported, failed


def _relative_failure_path(repo_path: str, path: str) -> str | None:
    """Return an API-safe, in-root relative path without resolving symlinks."""
    try:
        relative = os.path.relpath(os.path.abspath(path), os.path.abspath(repo_path))
    except ValueError:
        return None
    parts = relative.split(os.sep)
    if not parts or any(part in {"", ".", ".."} for part in parts):
        return None
    # Encode separators, drive-like colons, controls and percent signs that are
    # unsafe or ambiguous in the public failure schema while retaining identity.
    return "/".join(quote(part, safe="-._~ ") for part in parts)


def scan_with_metrics(
    repo_path: str, progress_callback: Callable[[dict[str, int]], None] | None = None,
) -> tuple[dict[tuple[str, str], list[dict[str, Any]]], dict[str, Any]]:
    """Run every collector and return evidence plus measured scope/coverage metrics."""
    started = time.perf_counter()
    if not os.path.isdir(repo_path):
        raise ValueError(f"Repository path does not exist: {repo_path}")
    profile = _scan_profile()
    evidence_limit = max_evidence_count()
    all_files, supported, failure_codes = _inventory(repo_path, profile)
    evidence_count = 0
    combined: dict[tuple[str, str], list[dict[str, Any]]] = {}
    ast_collector, rule_collector = ASTCollector(), RuleCollector()
    dep_collector, cert_collector = DepCollector(), CertCollector()
    collector_stats = dict.fromkeys(("ast", "rule", "dep", "cert"), 0)
    failed_paths = set(failure_codes)
    last_progress = started

    def report(processed: int) -> None:
        if progress_callback is not None:
            progress_callback({**collector_stats, "_files_processed": processed,
                               "_files_total": len(supported)})

    _print("=== ECDAT discovery-assurance scan starting ===")
    _print(f"Target: {_safe_filename(repo_path)} ({repo_path})")
    report(0)
    duration_budget = scan_duration_budget_ms()
    mem_budget_code = check_memory_budget()
    if mem_budget_code:
        failure_codes[repo_path] = mem_budget_code
        failed_paths.add(repo_path)
    # All collectors use the same declared scope; do not walk the tree four times.
    for index, path in enumerate(sorted(supported), 1):
        if path not in failed_paths:
            if duration_budget > 0 and (time.perf_counter() - started) * 1000 >= duration_budget:
                failure_codes[path] = "duration_budget_exceeded"
                failed_paths.add(path)
                continue
            if check_memory_budget():
                failure_codes[path] = "memory_budget_exceeded"
                failed_paths.add(path)
                continue
            ext = os.path.splitext(path)[1].lower()
            filename = os.path.basename(path)
            handlers = []
            if ext == ".py":
                handlers.append(("ast", ast_collector.scan_file))
            if ext in CODE_EXTENSIONS:
                handlers.append(("rule", rule_collector.scan_file))
            if filename == "requirements.txt":
                handlers.append(("dep", dep_collector.scan_requirements))
            if filename == "pom.xml":
                handlers.append(("dep", dep_collector.scan_pom_xml))
            if filename == "package-lock.json":
                handlers.append(("dep", dep_collector.scan_package_lock))
            if filename == "Gemfile.lock":
                handlers.append(("dep", dep_collector.scan_gemfile_lock))
            if filename == "go.sum":
                handlers.append(("dep", dep_collector.scan_go_sum))
            if filename == "Cargo.lock":
                handlers.append(("dep", dep_collector.scan_cargo_lock))
            if ext in {".crt", ".pem", ".cer"}:
                handlers.append(("cert", cert_collector.scan_cert))
            for name, handler in handlers:
                def record_failure(failed_path: str, collector: str = name) -> None:
                    failed_paths.add(failed_path)
                    failure_codes.setdefault(
                        failed_path,
                        "certificate_error" if collector == "cert" else "parse_error",
                    )

                assets = handler(path, on_error=record_failure)
                if evidence_count + len(assets) > evidence_limit:
                    raise ValueError("Scan exceeds configured evidence count limit")
                for asset in assets:
                    item = asset.to_dict()
                    item["evidence"] = redact_evidence(item.get("evidence", {}))
                    combined.setdefault((asset.algorithm, asset.location), []).append(item)
                    collector_stats[name] += 1
                    evidence_count += 1
        now = time.perf_counter()
        if now - last_progress >= 1.0 or index == len(supported):
            report(index)
            last_progress = now
    scanned = max(0, len(supported) - len(failed_paths))
    coverage = round(scanned / len(supported) * 100, 2) if supported else 0.0
    blind_spots = [
        "Runtime-generated cryptography is outside static scan scope",
        "Compiled binaries and obfuscated bytecode require binary analysis",
        "Container images, cloud services, network traffic and HSMs are not inspected",
        ("Source profile excludes .git, node_modules, dist, build, __pycache__, .venv, venv and env directories"
         if profile == "source" else
         "Environment profile excludes .git, node_modules, dist, build and __pycache__ directories"),
        "Coverage measures files processed without reported collector errors, not detection completeness",
        "Linked directories/files are excluded; oversized files count as processing failures",
    ]
    if not supported:
        blind_spots.append("No supported files were found; coverage is not established")
    if failed_paths:
        blind_spots.append(f"{len(failed_paths)} supported file(s) had read or parser errors; evidence may be partial")
    if duration_budget > 0:
        blind_spots.append(f"Scan duration capped at {duration_budget / 1000:.0f}s; remaining files skipped on budget exhaustion")
    if scan_memory_budget_mb() > 0:
        blind_spots.append(f"Memory budget of {scan_memory_budget_mb()} MB enforced; remaining files skipped on budget exhaustion")
    failures: list[dict[str, str]] = []
    for path in sorted(failed_paths):
        relative = _relative_failure_path(repo_path, path)
        if relative is not None:
            failures.append({"path": relative, "reason": failure_codes.get(path, "parse_error")})
    metrics = {
        "total_files": len(all_files), "in_scope_files": len(supported),
        "scanned_files": scanned, "failed_files": len(failed_paths),
        "coverage_pct": coverage, "collector_stats": collector_stats,
        "blind_spots": blind_spots,
        "failures": failures,
        "duration_ms": round((time.perf_counter() - started) * 1000),
    }
    total = sum(len(value) for value in combined.values())
    _print(f"=== Scan complete: {total} evidences, {coverage:.1f}% supported-file coverage ===")
    return combined, metrics


def scan(repo_path: str) -> dict[tuple[str, str], list[dict[str, Any]]]:
    """
    Walk a repository and discover cryptographic assets using all collectors.

    Returns:
        dict keyed by (algorithm, filepath) -> list of evidence dicts. Each
        evidence dict has shape:
            {
              "algorithm": str,
              "category": str,
              "source": "ast" | "dep" | "cert",
              "location": str,
              "evidence": dict,
              "confidence": float,
              ...
            }
    """
    try:
        evidence, _metrics = scan_with_metrics(repo_path)
        return evidence
    except ValueError as exc:
        _print(f"ERROR: {exc}")
        return {}


def scan_to_dict(repo_path: str) -> list[dict[str, Any]]:
    """Return evidence as a list of dicts (convenience for downstream code)."""
    grouped = scan(repo_path)
    flat: list[dict[str, Any]] = []
    for evs in grouped.values():
        flat.extend(evs)
    return flat


def _cli_main() -> None:
    parser = argparse.ArgumentParser(description="ECDAT scanner")
    parser.add_argument("repo_path", help="Path to repository or directory")
    parser.add_argument("--output", "-o", default=None,
                        help="Write evidence JSON to this file")
    args = parser.parse_args()

    start = time.time()
    evidences = scan_to_dict(args.repo_path)
    elapsed = time.time() - start

    _print(f"Elapsed: {elapsed:.2f}s")

    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)) or ".",
                    exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as fh:
            json.dump(evidences, fh, indent=2)
        _print(f"Wrote {args.output}")
    else:
        _scanner_logger.info("Evidence sample", extra={"extra_data": {"count": min(3, len(evidences)), "sample": evidences[:3]}})


if __name__ == "__main__":
    _cli_main()
