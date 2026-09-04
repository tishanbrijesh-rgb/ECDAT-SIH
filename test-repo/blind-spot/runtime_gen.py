"""
blind-spot/runtime_gen.py — demonstrates a gap in static analysis.

This file dynamically loads a crypto module and calls it via getattr,
which an AST scanner cannot resolve without full interprocedural analysis.

THIS IS A BLIND SPOT: the scanner will NOT detect the crypto usage here.
"""

from __future__ import annotations

import importlib


def _load_crypto_module(name: str):
    """Dynamically import a crypto module by name."""
    return importlib.import_module(name)


def _load_and_encrypt(module_name: str, function_name: str, data: bytes) -> bytes:
    """
    Resolve a function at runtime and call it.
    Static analysis tools cannot determine what module/function is used.
    """
    mod = _load_crypto_module(module_name)
    fn = getattr(mod, function_name)
    return fn(data)


def runtime_encrypt(data: bytes) -> bytes:
    # Calls AES.new from PyCryptodome at runtime
    return _load_and_encrypt(
        "Crypto.Cipher.AES",
        "new",
        b"\x00" * 32,  # dummy key
    ).encrypt(data)


def runtime_hash(data: bytes) -> str:
    import hashlib
    h = _load_crypto_module("hashlib").sha256(data)
    return h.hexdigest()


def obfuscated_crypto(data: bytes) -> bytes:
    """Base64-encoded string trickery — AST scanner will see a string but
    not know it decodes to a module name."""
    import base64
    encoded = "Q3lwdG8uQ2lwaGVyLkFFUw=="  # "Crypto.Cipher.AES"
    mod_name = base64.b64decode(encoded).decode()
    return _load_and_encrypt(mod_name, "new", b"\x00" * 32).encrypt(data)
