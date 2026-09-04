"""
AST-based static analysis collector. Walks Python AST to detect
cryptographic imports, function calls, and variable assignments.
"""

from __future__ import annotations

import ast
import os

from scanner.models.asset import CryptoAsset
from scanner.rules.crypto_patterns import get_category

# ---------------------------------------------------------------------------
# Known crypto library imports mapped to algorithms
# ---------------------------------------------------------------------------
_CRYPTO_IMPORTS: dict[str, str] = {
    # PyCryptodome / PyCrypto
    "Crypto.Cipher.AES": "AES",
    "Crypto.Cipher.PKCS1_OAEP": "RSA",
    "Crypto.Cipher._mode_gcm.GcmMode": "AES",
    "Crypto.Cipher._mode_cbc.CbcMode": "AES",
    "Crypto.Cipher.DES3": "3DES",
    "Crypto.Signature.PKCS1_v1_5": "RSA",
    "Crypto.PublicKey.RSA": "RSA",
    "Crypto.PublicKey.ECC": "ECDSA",
    "Crypto.Hash.SHA256": "SHA-256",
    "Crypto.Hash.SHA512": "SHA-512",
    "Crypto.Hash.MD5": "MD5",
    "Crypto.Hash.BLAKE2": "BLAKE2",
    "Crypto.Signature.ed25519": "Ed25519",
    "Crypto.Random": "RNG",
    # cryptography library
    "cryptography.hazmat.primitives.ciphers": "AES",
    "cryptography.hazmat.primitives.ciphers.modes": "AES",
    "cryptography.hazmat.primitives.ciphers.algorithms": "AES",
    "cryptography.hazmat.primitives.asymmetric.rsa": "RSA",
    "cryptography.hazmat.primitives.asymmetric.ec": "ECDSA",
    "cryptography.hazmat.primitives.asymmetric.padding": "RSA",
    "cryptography.hazmat.primitives.asymmetric.ed25519": "Ed25519",
    "cryptography.hazmat.primitives.kdf": "KDF",
    # ssl / cryptography.x509
    "ssl": "TLS",
    "cryptography.x509": "X509",
}

class _CryptoVisitor(ast.NodeVisitor):
    """Walks AST nodes and records crypto-related findings."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.assets: list[CryptoAsset] = []
        self.bindings: dict[str, str | None] = {}

    def _resolve(self, node: ast.expr) -> str:
        if isinstance(node, ast.Name):
            return self.bindings.get(node.id) or ""
        if isinstance(node, ast.Attribute):
            parent = self._resolve(node.value)
            return f"{parent}.{node.attr}" if parent else ""
        return ""

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            self.bindings[node.id] = None

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            root = node.value
            while isinstance(root, ast.Attribute):
                root = root.value
            if isinstance(root, ast.Name):
                self.bindings[root.id] = None
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        self.visit(node.value)
        for target in node.targets:
            self.visit(target)

    def _visit_function(self, node) -> None:
        # Defaults/decorators execute in the enclosing scope; arguments and
        # locally assigned names shadow imports throughout the function body.
        for value in [*node.decorator_list, *node.args.defaults,
                      *[v for v in node.args.kw_defaults if v is not None]]:
            self.visit(value)
        self.bindings[node.name] = None
        outer = self.bindings
        self.bindings = outer.copy()
        args = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
        for arg in [*args, node.args.vararg, node.args.kwarg]:
            if arg is not None:
                self.bindings[arg.arg] = None
        # Do not descend into nested scopes when collecting local declarations.
        def locals_in(nodes):
            for child in nodes:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    yield child.name
                elif isinstance(child, (ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                    continue
                elif isinstance(child, ast.Import):
                    for alias in child.names:
                        yield alias.asname or alias.name.split('.')[0]
                elif isinstance(child, ast.ImportFrom):
                    for alias in child.names:
                        yield alias.asname or alias.name
                elif isinstance(child, ast.Name) and isinstance(child.ctx, (ast.Store, ast.Del)):
                    yield child.id
                else:
                    yield from locals_in(ast.iter_child_nodes(child))
        for name in locals_in(node.body):
            self.bindings[name] = None
        for statement in node.body:
            self.visit(statement)
        self.bindings = outer

    visit_FunctionDef = _visit_function
    visit_AsyncFunctionDef = _visit_function

    def visit_Lambda(self, node: ast.Lambda) -> None:
        for value in [*node.args.defaults, *[v for v in node.args.kw_defaults if v is not None]]:
            self.visit(value)
        outer = self.bindings
        self.bindings = outer.copy()
        for arg in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs,
                    node.args.vararg, node.args.kwarg]:
            if arg is not None:
                self.bindings[arg.arg] = None
        self.visit(node.body)
        self.bindings = outer

    def _visit_comprehension(self, node) -> None:
        outer = self.bindings
        self.bindings = outer.copy()
        for generator in node.generators:
            self.visit(generator.iter)
            self.visit(generator.target)
            for condition in generator.ifs:
                self.visit(condition)
        if isinstance(node, ast.DictComp):
            self.visit(node.key)
            self.visit(node.value)
        else:
            self.visit(node.elt)
        self.bindings = outer

    visit_ListComp = _visit_comprehension
    visit_SetComp = _visit_comprehension
    visit_DictComp = _visit_comprehension
    visit_GeneratorExp = _visit_comprehension

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.bindings[node.name] = None
        outer = self.bindings
        self.bindings = outer.copy()
        self.generic_visit(node)
        self.bindings = outer

    # ---- import handling ---------------------------------------------------

    def _record_import(self, full_name: str, node: ast.AST, line_no: int) -> None:
        algo = _CRYPTO_IMPORTS.get(full_name)
        if algo is None:
            return
        cat = "hash" if algo == "hash" else get_category(algo)
        evidence = {
            "import": full_name,
            "node_type": type(node).__name__,
            "line": line_no,
        }
        self.assets.append(
            CryptoAsset(
                algorithm=algo,
                category=cat,
                source="ast",
                location=self.filepath,
                evidence=evidence,
                confidence=0.90,
            )
        )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802
        if node.module is not None and node.level == 0:
            full_name = node.module
            self._record_import(full_name, node, node.lineno)
            # Also check submodule imports  e.g. from cryptography.hazmat... import X
            for alias in node.names:
                sub = f"{full_name}.{alias.name}"
                self.bindings[alias.asname or alias.name] = sub
                self._record_import(sub, node, node.lineno)
        else:
            for alias in node.names:
                self.bindings[alias.asname or alias.name] = None
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:  # noqa: N802
        for alias in node.names:
            self.bindings[alias.asname or alias.name.split('.')[0]] = (
                alias.name if alias.asname else alias.name.split('.')[0])
            self._record_import(alias.name, node, node.lineno)
        self.generic_visit(node)

    # ---- call handling -----------------------------------------------------

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        func_name = self._resolve(node.func)
        hashes = {"sha256": "SHA-256", "sha512": "SHA-512", "sha1": "SHA-1",
                  "md5": "MD5", "blake2b": "BLAKE2", "blake2s": "BLAKE2"}
        algorithm = None
        category, usage = "hash", "hashing"
        if func_name.startswith("hashlib."):
            name = func_name.removeprefix("hashlib.")
            if name == "new":
                selector = node.args[0] if node.args else next(
                    (kw.value for kw in node.keywords if kw.arg == "name"), None)
                if isinstance(selector, ast.Constant) and isinstance(selector.value, str):
                    name = selector.value.lower().replace("-", "")
            algorithm = hashes.get(name)
        elif func_name.startswith("cryptography.hazmat.primitives.hashes."):
            algorithm = hashes.get(func_name.rsplit('.', 1)[-1].lower())
        elif func_name in {"hmac.new", "hmac.digest"}:
            selector = node.args[2] if len(node.args) > 2 else next(
                (kw.value for kw in node.keywords if kw.arg in {"digestmod", "digest"}), None)
            if isinstance(selector, ast.Constant) and isinstance(selector.value, str):
                algorithm = hashes.get(selector.value.lower().replace('-', ''))
            elif selector is not None:
                resolved = self._resolve(selector)
                if resolved.startswith('hashlib.'):
                    algorithm = hashes.get(resolved.removeprefix('hashlib.'))
        elif func_name in {
            "cryptography.hazmat.primitives.asymmetric.padding.OAEP",
            "cryptography.hazmat.primitives.asymmetric.padding.PKCS1v15",
            "Crypto.Cipher.PKCS1_OAEP.new",
        }:
            algorithm, category, usage = "RSA", "encryption", "unknown"
        if algorithm:
            self.assets.append(CryptoAsset(
                algorithm=algorithm, category=category, source="ast",
                location=self.filepath, confidence=0.90,
                evidence={"call": func_name, "line": node.lineno,
                          "column": node.col_offset, "usage": usage,
                          "operation_id": f"python-call:{node.lineno}:{node.col_offset}"},
            ))
        self.generic_visit(node)


class ASTCollector:
    """AST-based static analysis collector for Python source files."""

    def scan_file(self, path: str, on_error=None) -> list[CryptoAsset]:
        """Parse a Python file and return detected crypto assets."""
        assets: list[CryptoAsset] = []
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                source = fh.read()
            tree = ast.parse(source)
            visitor = _CryptoVisitor(path)
            visitor.visit(tree)
            assets = visitor.assets
        except (SyntaxError, OSError, ValueError, RecursionError):
            if on_error is not None:
                on_error(path)
        return assets

    def scan_directory(self, root: str) -> dict[tuple[str, str], list[dict]]:
        """Scan all .py files under root, return dict keyed by (algorithm, filepath)."""
        results: dict[tuple[str, str], list[dict]] = {}
        for dirpath, _dirnames, filenames in os.walk(root):
            for fname in filenames:
                if not fname.endswith(".py"):
                    continue
                full_path = os.path.join(dirpath, fname)
                file_assets = self.scan_file(full_path)
                for asset in file_assets:
                    key = (asset.algorithm, asset.location)
                    results.setdefault(key, []).append(asset.to_dict())
        return results
