"""Custom wrapper around the cryptography library Fernet."""
from cryptography.fernet import Fernet as _Fernet

Fernet = _Fernet  # alias for mypy compatibility


class MyCipher:
    """Thin wrapper that exposes encrypt/decrypt."""

    def __init__(self, key: bytes | None = None):
        if key is None:
            key = Fernet.generate_key()
        self._fernet = _Fernet(key)

    def encrypt(self, plaintext: bytes) -> bytes:
        return self._fernet.encrypt(plaintext)

    def decrypt(self, token: bytes) -> bytes:
        return self._fernet.decrypt(token)


class EncryptedStorage:
    """Higher-level storage wrapper using MyCipher."""

    def __init__(self, cipher: MyCipher):
        self._cipher = cipher
        self._store: dict[str, bytes] = {}

    def put(self, key: str, value: str) -> None:
        self._store[key] = self._cipher.encrypt(value.encode())

    def get(self, key: str) -> str:
        return self._cipher.decrypt(self._store[key]).decode()
