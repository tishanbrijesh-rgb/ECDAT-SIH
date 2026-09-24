"""
Collector registry — single source of truth mapping file names and extensions
to the collector handler that processes them.

Both _inventory() (which decides whether a file is "in scope") and
scan_with_metrics() (which dispatches to a handler) read from this registry,
so supported-file routing cannot drift apart.
"""
from __future__ import annotations

import os
from collections.abc import Callable

from scanner.collectors.ast_collector import ASTCollector
from scanner.collectors.cert_collector import CertCollector
from scanner.collectors.dep_collector import DepCollector
from scanner.collectors.rule_collector import CODE_EXTENSIONS, RuleCollector


class CollectorRegistry:
    """Maps file extensions and filenames to (collector_name, handler) tuples.

    The same registry instance is shared between inventory and the main scan
    loop so the two cannot disagree about which files are supported.
    """

    def __init__(self) -> None:
        self._ast = ASTCollector()
        self._rule = RuleCollector()
        self._dep = DepCollector()
        self._cert = CertCollector()

        # Extension-based registrations (lowercase, include the dot).
        # A single extension can map to multiple handlers (e.g. ".py" maps
        # to both the AST and rule collectors).  Each value is a list so
        # that filename matches and extension matches can be merged without
        # losing handlers.
        self._extensions: dict[str, list[tuple[str, Callable]]] = {
            ".py": [("ast", self._ast.scan_file)],
        }

        # Filename-based registrations (exact match; lookup is exact after
        # the caller normalises via os.path.basename).
        self._filenames: dict[str, tuple[str, Callable]] = {
            # Dependency manifests / lockfiles.
            "requirements.txt":  ("dep", self._dep.scan_requirements),
            "pom.xml":           ("dep", self._dep.scan_pom_xml),
            "package-lock.json": ("dep", self._dep.scan_package_lock),
            "Gemfile.lock":      ("dep", self._dep.scan_gemfile_lock),
            "go.sum":            ("dep", self._dep.scan_go_sum),
            "Cargo.lock":        ("dep", self._dep.scan_cargo_lock),
        }

        # Additional extensions registered after the filename map so they
        # don't shadow specific lockfile handling.
        for ext in CODE_EXTENSIONS:
            self._extensions.setdefault(ext, []).append(("rule", self._rule.scan_file))
        for ext in (".crt", ".pem", ".cer"):
            self._extensions.setdefault(ext, []).append(("cert", self._cert.scan_cert))

    # ------------------------------------------------------------------
    # Inventory helpers — these return the *sets* _inventory() needs.
    # ------------------------------------------------------------------
    @property
    def supported_extensions(self) -> set[str]:
        """Extensions that mark a file as in-scope."""
        return set(self._extensions.keys())

    @property
    def supported_filenames(self) -> set[str]:
        """Exact filenames that mark a file as in-scope."""
        return set(self._filenames.keys())

    # ------------------------------------------------------------------
    # Dispatch — returns handler tuples for a given path.
    # ------------------------------------------------------------------
    def handlers_for(self, path: str) -> list[tuple[str, Callable]]:
        """Return (collector_name, handler) tuples for *path*.

        Filename matches take priority over extension matches. A file
        whose name matches the registry gets its named handler first;
        extension-based handlers are appended afterward (so e.g. a .java
        file still gets the rule collector).  Within each group, the same
        collector name appears at most once (first match wins).
        """
        result: list[tuple[str, Callable]] = []
        seen: set[str] = set()
        filename = os.path.basename(path)
        if filename in self._filenames:
            name, handler = self._filenames[filename]
            result.append((name, handler))
            seen.add(name)
        ext = os.path.splitext(filename)[1].lower()
        if ext in self._extensions:
            for name, handler in self._extensions[ext]:
                if name not in seen:
                    result.append((name, handler))
                    seen.add(name)
        return result
