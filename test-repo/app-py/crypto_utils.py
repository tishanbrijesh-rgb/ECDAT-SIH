"""
crypto_utils.py — Example Python app using cryptographic primitives.

Demonstrates: AES-GCM encryption, RSA-OAEP key wrapping,
SHA-256 hashing, and HMAC authentication.
"""

from __future__ import annotations

import hashlib
import hmac
import os

from Crypto.Cipher import AES
from Crypto.Cipher import PKCS1_OAEP
from Crypto.PublicKey import RSA
from Crypto.Random import get_random_bytes
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import serialization


class SecureEncryptor:
    """Handles symmetric encryption with AES-GCM."""

    def __init__(self, key: bytes | None = None):
        self.key = key or get_random_bytes(32)  # 256-bit

    def encrypt(self, plaintext: bytes) -> tuple[bytes, bytes, bytes]:
        cipher = AES.new(self.key, AES.MODE_GCM)
        ciphertext, tag = cipher.encrypt_and_digest(plaintext)
        return ciphertext, cipher.nonce, tag

    def decrypt(self, ciphertext: bytes, nonce: bytes, tag: bytes) -> bytes:
        cipher = AES.new(self.key, AES.MODE_GCM, nonce=nonce)
        return cipher.decrypt_and_verify(ciphertext, tag)


class RSAKeyWrapping:
    """Wraps symmetric keys with RSA-OAEP."""

    def __init__(self):
        self.key = RSA.generate(2048)
        self.pub_pem = self.key.publickey().export_key()
        self.cipher = PKCS1_OAEP.new(self.key)

    def wrap_key(self, sym_key: bytes) -> bytes:
        return self.cipher.encrypt(sym_key)

    def unwrap_key(self, wrapped: bytes) -> bytes:
        return self.cipher.decrypt(wrapped)


class HashVerifier:
    """Computes SHA-256 and SHA-512 digests."""

    @staticmethod
    def sha256(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def sha512(data: bytes) -> str:
        return hashlib.sha512(data).hexdigest()

    @staticmethod
    def hmac_sha256(key: bytes, msg: bytes) -> str:
        return hmac.new(key, msg, hashlib.sha256).hexdigest()


class ECDSASigner:
    """ECDSA P-256 signing and verification using cryptography library."""

    def __init__(self):
        self.private_key = ec.generate_private_key(ec.SECP256R1())
        self.public_key = self.private_key.public_key()

    def sign(self, data: bytes) -> bytes:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import utils
        return self.private_key.sign(
            data,
            ec.ECDSA(hashes.SHA256()),
        )

    def verify(self, data: bytes, signature: bytes) -> bool:
        from cryptography.hazmat.primitives import hashes
        try:
            self.public_key.verify(signature, data, ec.ECDSA(hashes.SHA256()))
            return True
        except Exception:
            return False


class KeyDeriver:
    """PBKDF2 key derivation using SHA-256."""

    @staticmethod
    def derive_key(password: bytes, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100_000,
        )
        return kdf.derive(password)


# ── Module-level one-time setup ──────────────────────────────────────────────
_aes_key = hashlib.sha256(b"demo-static-key").digest()
_encryptor = SecureEncryptor(_aes_key)
