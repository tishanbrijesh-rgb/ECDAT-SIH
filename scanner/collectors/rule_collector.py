"""Auditable multi-language rule collector used as independent scan evidence."""

from __future__ import annotations

import os
import re
import io
import tokenize
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
    """Preserve line numbers and avoid treating quoted URLs as comments."""
    if extension == ".py":
        # Text literals are not observed crypto use. Recognized string-selected
        # hash calls are handled structurally by ASTCollector.
        tokens = []
        try:
            for token in tokenize.generate_tokens(io.StringIO(text).readline):
                if token.type in {tokenize.STRING, tokenize.COMMENT}:
                    token = token._replace(string=re.sub(r"[^\n\r]", " ", token.string))
                tokens.append(token)
        except (tokenize.TokenError, IndentationError):
            # Retain only the safely tokenized prefix; AST reports the error.
            pass
        return tokenize.untokenize(tokens)
    pattern = r'''"""[\s\S]*?"""|`(?:\\.|[^`\\])*`|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|//[^\n]*|/\*[\s\S]*?\*/'''
    # Keep literals only in recognized algorithm-selector positions. A printed
    # code example is one outer string token, never executable source.
    output, end, prefix = [], 0, ""
    for match in re.finditer(pattern, text):
        segment = text[end:match.start()]
        output.append(segment)
        prefix = (prefix + segment)[-160:]
        selector = re.search(
            r'(?:\b(?:Cipher|Signature|MessageDigest|KeyGenerator|KeyPairGenerator|SSLContext)'
            r'\s*\.\s*getInstance|\b(?:createHash|createHmac|ECGenParameterSpec))\s*\(\s*$', prefix)
        token = match.group(0)
        keep = selector and token.startswith(('"', "'")) and not token.startswith('"""')
        masked = token if keep else re.sub(r"[^\n\r]", " ", token)
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


def _statements(text: str):
    """Separate same-line statements without splitting quoted selector values."""
    for line_no, line in enumerate(text.splitlines(), 1):
        start = 0
        for match in re.finditer(r'''"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|;''', line):
            if match.group() == ';':
                yield line_no, start, line[start:match.start()]
                start = match.end()
        yield line_no, start, line[start:]


class RuleCollector:
    """Scans supported source languages using transparent JSON regex rules."""

    confidence = 0.82

    def scan_file(self, path: str, on_error=None) -> list[CryptoAsset]:
        extension = Path(path).suffix.lower()
        if extension not in CODE_EXTENSIONS:
            return []
        try:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
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
                # Python hashes have binding-aware AST evidence. Lexical name
                # hits are not independent observations and must not duplicate
                # calls or revive shadowed/non-crypto names.
                if extension == ".py" and config.get("category") == "hash":
                    continue
                for pattern in config.get("patterns", []):
                    try:
                        matched = re.search(pattern, line, flags=re.I)
                    except re.error:
                        matched = re.search(re.escape(pattern), line, flags=re.I)
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
                            "line": line_no,
                            "column": column,
                            "snippet": line.strip()[:240],
                            "usage": usage,
                            "library": library,
                            "protocol": "TLS" if usage == "tls" else "",
                            "key_size": _key_size(line, algorithm),
                            "operation_id": f"{path}:{line_no}:{column}:{usage}",
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
