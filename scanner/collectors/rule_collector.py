"""Auditable multi-language rule collector used as independent scan evidence."""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from scanner.limits import read_text
from scanner.models.asset import CryptoAsset
from scanner.rules.crypto_patterns import load_rules

CODE_EXTENSIONS = {".py", ".java", ".js", ".ts", ".c", ".cpp", ".go", ".cs", ".rs"}


def _usage(line: str, algorithm: str) -> str:
    value = line.lower()
    if algorithm in {"SHA-256", "SHA-512", "SHA-1", "MD5", "BLAKE2"}:
        return "hashing"
    if algorithm in {"ECDSA", "DSA", "Ed25519", "ML-DSA"}:
        return "signature"
    if algorithm in {"ECDH", "DH", "ML-KEM"}:
        return "key_establishment"
    if algorithm in {"AES", "ChaCha20"}:
        return "encryption"
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
    """Preserve line numbers and avoid treating quoted URLs as comments."""
    pattern = r'''"""[\s\S]*?"""|`(?:\\.|[^`\\])*`|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|//[^\n]*|/\*[\s\S]*?\*/'''
    if extension == ".py":
        pattern += r"|#[^\n]*"
    output, end, prefix = [], 0, ""
    for match in re.finditer(pattern, text):
        segment = text[end:match.start()]
        output.append(segment)
        prefix = (prefix + segment)[-160:]
        selector = re.search(
            r'(?:\b(?:Cipher|Signature|MessageDigest|KeyGenerator|KeyPairGenerator|SSLContext)'
            r'\s*\.\s*getInstance|\b(?:createHash|createHmac|ECGenParameterSpec|generateKeyPairSync))\s*\(\s*$', prefix)
        literal = match.group(0)
        keep = selector and literal.startswith(('"', "'")) and not literal.startswith('"""')
        masked = literal if keep else re.sub(r"[^\n\r]", " ", literal)
        output.append(masked)
        prefix = (prefix + masked)[-160:]
        end = match.end()
    output.append(text[end:])
    return ''.join(output)


def _key_size(line: str, algorithm: str) -> int | None:
    """Read explicit API arguments only, never an unrelated number on the line."""
    patterns = {
        "AES": [r'''\bKeyGenerator\s*\.\s*getInstance\(\s*["']AES["']\s*\)\s*\.\s*init\(\s*(128|192|256)\s*\)'''],
        "RSA": [r'\bRSA\.generate\(\s*(1024|2048|3072|4096|8192)\s*[,)]',
                r'\brsa\.generate_private_key\([^)]*\bkey_size\s*=\s*(1024|2048|3072|4096|8192)\s*[,)]'],
    }
    sizes = {int(match.group(1)) for pattern in patterns.get(algorithm, [])
             for match in re.finditer(pattern, line)}
    return sizes.pop() if len(sizes) == 1 else None


def _statements(text: str) -> Iterator[tuple[int, int, str]]:
    """Separate same-line statements without splitting quoted selector values."""
    for line_no, line in enumerate(text.splitlines(), 1):
        start = 0
        for match in re.finditer(r'''"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|;''', line):
            if match.group() == ';':
                yield line_no, start, line[start:match.start()]
                start = match.end()
        yield line_no, start, line[start:]


def _java_hash_non_operation(line: str) -> bool:
    """Reject declarations and nested MAC construction from hash call matching."""
    value = line.strip()
    modified_declaration = re.match(
        r'^(?:(?:public|private|protected|static|final|synchronized|abstract|native|default)\s+)+'
        r'(?:[\w<>\[\].,?]+\s+)?\w+\s*\([^;]*\)\s*(?:throws\s+[^{}]+)?(?:\{|\{\s*\})?\s*$',
        value,
    )
    digest_constructor = re.match(
        r'^(?:SHA1|SHA256|SHA512|MD5)Digest\s*\([^;{}]*\)\s*'
        r'(?:throws\s+[^{}]+)?(?:\{|\{\s*\})?\s*$',
        value,
        re.IGNORECASE,
    )
    interface_declaration = None
    if not re.match(r'^(?:return|new|throw|yield)\b', value):
        interface_declaration = re.match(
            r'^[\w<>\[\].,?]+\s+\w+\s*\([^;{}]*\)\s*'
            r'(?:throws\s+[^{}]+)?(?:\{|\{\s*\})?\s*$',
            value,
        )
    nested_mac = re.search(r'\b(?:Old)?HMac\s*\(', value)
    return bool(modified_declaration or digest_constructor or interface_declaration or nested_mac)


def _java_field_declaration(line: str) -> bool:
    """Reject Java declarations that do not invoke or assign crypto operations."""
    return bool(re.match(
        r"^\s*(?:(?:public|private|protected|static|final|volatile|transient)\s+)*"
        r"[\w<>\[\].,?]+\s+\w+\s*$",
        line,
    ))


def _algorithm_named_assignment(line: str, algorithm: str) -> bool:
    """Reject configuration symbols named after an algorithm, not its use."""
    name = re.escape(algorithm.replace("-", "[_-]?"))
    declaration = re.match(
        rf"^\s*(?:(?:public|private|protected|static|final|const|let|var|volatile|transient)\s+)*"
        rf"(?:[\w<>\[\].,?]+\s+)?{name}\s*=\s*(.*)$",
        line,
        re.IGNORECASE,
    )
    if not declaration:
        return False
    return re.search(name, declaration.group(1), re.IGNORECASE) is None


class RuleCollector:
    """Scans supported source languages using transparent JSON regex rules."""

    confidence: float = 0.82

    def scan_file(self, path: str, on_error: Callable[[str], None] | None = None) -> list[CryptoAsset]:
        extension = Path(path).suffix.lower()
        if extension not in CODE_EXTENSIONS:
            return []
        try:
            text = read_text(path, errors="replace")
        except OSError:
            if on_error is not None:
                on_error(path)
            return []
        text = _strip_comments(text, extension)
        rules = load_rules().get("algorithms", {})
        assets: list[CryptoAsset] = []
        seen: set[tuple[str, int, int]] = set()
        dynamic_depth = 0
        for line_no, column, line in _statements(text):
            dynamic_marker = any(marker in line for marker in ("import_module(", "getattr(", "base64.b64decode", "_load_crypto_module(", "_load_and_encrypt("))
            if dynamic_marker or dynamic_depth > 0:
                dynamic_depth += line.count("(") - line.count(")")
                dynamic_depth = max(0, dynamic_depth)
                continue
            for algorithm, config in rules.items():
                if _algorithm_named_assignment(line, algorithm):
                    continue
                if extension == ".java" and _java_field_declaration(line):
                    continue
                # Python hash and HMAC calls are binding-aware AST detections.
                # Regex evidence would duplicate them and revive shadowed names.
                if extension == ".py" and (
                    config.get("category") == "hash" or algorithm == "HMAC"
                ):
                    continue
                if extension == '.java' and config.get('category') == 'hash':
                    if '(' not in line or re.match(
                        r'^\s*(?:(?:public|private|protected|static|final|synchronized|abstract|native)\s+)+'
                        r'(?:[\w<>\[\].]+\s+)?\w+\s*\([^;]*\)\s*(?:throws\s+[^{}]+)?\{\s*$', line):
                        continue
                    if _java_hash_non_operation(line):
                        continue
                patterns = list(config.get(
                    "java_patterns" if extension == '.java' and config.get('category') == 'hash'
                    else "patterns", []))
                for pattern in patterns:
                    try:
                        matched = re.search(pattern, line, flags=re.IGNORECASE)
                    except re.error:
                        matched = re.search(re.escape(pattern), line, flags=re.IGNORECASE)
                    if not matched or (algorithm, line_no, column) in seen:
                        continue
                    seen.add((algorithm, line_no, column))
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
                    assets.append(CryptoAsset(
                        algorithm=algorithm,
                        category=config.get("category", "unknown"),
                        source="rule",
                        location=path,
                        evidence={
                            "rule_id": f"crypto.{algorithm.lower().replace('-', '_')}",
                            "pattern": pattern,
                            "snippet": line.strip()[:240],
                            "library": library,
                            "protocol": "TLS" if usage == "tls" else "",
                            "key_size": _key_size(line, algorithm),
                            "usage": usage,
                        },
                        confidence=self.confidence,
                        evidence_kind="observed_operation",
                        parser_version="rule-v1",
                        span={"file": path, "line_start": line_no,
                              "line_end": line_no, "column_start": column,
                              "column_end": column + len(matched.group(0))},
                        confidence_reasons=[
                            {"source": "rule", "evidence_kind": "observed_operation",
                             "base": 0.82, "bonus": 0.0, "penalty": 0.0,
                             "note": "regex match against code pattern"}
                        ],
                    ))
                    break
        return assets

    def scan_directory(self, root: str) -> dict[tuple[str, str], list[dict[str, Any]]]:
        results: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in {".git", "node_modules", "dist", "build", "__pycache__"}]
            for filename in filenames:
                path = os.path.join(dirpath, filename)
                for asset in self.scan_file(path):
                    results.setdefault((asset.algorithm, asset.location), []).append(asset.to_dict())
        return results
