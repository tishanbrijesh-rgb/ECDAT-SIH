"""Auditable multi-language rule collector used as independent scan evidence."""

from __future__ import annotations

import os
import re
from pathlib import Path

from scanner.models.asset import CryptoAsset
from scanner.rules.crypto_patterns import load_rules

CODE_EXTENSIONS = {".py", ".java", ".js", ".ts", ".c", ".cpp", ".go", ".cs"}


def _usage(line: str, algorithm: str) -> str:
    value = line.lower()
    if any(word in value for word in ("sign", "verify", "signature")):
        return "signature"
    if any(word in value for word in ("digest", "hash", "sha", "md5")):
        return "hashing"
    if any(word in value for word in ("exchange", "derive", "kem", "agreement")):
        return "key_establishment"
    if algorithm == "TLS" or "tls" in value or "ssl" in value:
        return "tls"
    return "encryption"


def _strip_comments(text: str, extension: str) -> str:
    """Remove obvious comments while preserving line numbers."""
    if extension == ".py":
        text = re.sub(
            r"(?is)(?:r|u|b|f|br|rb)?(?:\"\"\".*?\"\"\"|'''.*?''')",
            lambda match: "\n" * match.group(0).count("\n"), text,
        )
        return "\n".join(line.split("#", 1)[0] for line in text.splitlines())
    text = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
    return "\n".join(line.split("//", 1)[0] for line in text.splitlines())


class RuleCollector:
    """Scans supported source languages using transparent JSON regex rules."""

    confidence = 0.82

    def scan_file(self, path: str) -> list[CryptoAsset]:
        extension = Path(path).suffix.lower()
        if extension not in CODE_EXTENSIONS:
            return []
        try:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return []
        text = _strip_comments(text, extension)
        rules = load_rules().get("algorithms", {})
        assets: list[CryptoAsset] = []
        seen: set[tuple[str, int]] = set()
        dynamic_depth = 0
        for line_no, line in enumerate(text.splitlines(), 1):
            dynamic_marker = any(marker in line for marker in ("import_module(", "getattr(", "base64.b64decode", "_load_crypto_module(", "_load_and_encrypt("))
            if dynamic_marker or dynamic_depth > 0:
                dynamic_depth += line.count("(") - line.count(")")
                dynamic_depth = max(0, dynamic_depth)
                continue
            for algorithm, config in rules.items():
                for pattern in config.get("patterns", []):
                    try:
                        matched = re.search(pattern, line, flags=re.I)
                    except re.error:
                        matched = re.search(re.escape(pattern), line, flags=re.I)
                    if not matched or (algorithm, line_no) in seen:
                        continue
                    seen.add((algorithm, line_no))
                    usage = _usage(line, algorithm)
                    library = ""
                    lowered = line.lower()
                    if "bouncycastle" in lowered:
                        library = "Bouncy Castle"
                    elif "openssl" in lowered:
                        library = "OpenSSL"
                    elif "cryptography" in lowered:
                        library = "Python cryptography"
                    elif "crypto." in lowered:
                        library = "PyCryptodome"
                    key_match = re.search(r"\b(128|192|2048|3072|4096)\b", line)
                    assets.append(CryptoAsset(
                        algorithm=algorithm,
                        category=config.get("category", "unknown"),
                        source="rule",
                        location=path,
                        evidence={
                            "rule_id": f"crypto.{algorithm.lower().replace('-', '_')}",
                            "pattern": pattern,
                            "line": line_no,
                            "snippet": line.strip()[:240],
                            "usage": usage,
                            "library": library,
                            "protocol": "TLS" if usage == "tls" else "",
                            "key_size": int(key_match.group(1)) if key_match else None,
                            "operation_id": f"{path}:{line_no}:{usage}",
                        },
                        confidence=self.confidence,
                    ))
                    break
        return assets

    def scan_directory(self, root: str) -> dict[tuple[str, str], list[dict]]:
        results: dict[tuple[str, str], list[dict]] = {}
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in {".git", "node_modules", "dist", "build", "__pycache__"}]
            for filename in filenames:
                path = os.path.join(dirpath, filename)
                for asset in self.scan_file(path):
                    results.setdefault((asset.algorithm, asset.location), []).append(asset.to_dict())
        return results
