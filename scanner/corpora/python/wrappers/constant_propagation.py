"""Constant propagation through multiple layers of indirection."""
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

# Constants defined at module level
SALT = b"\x01\x02\x03\x04\x05\x06\x07\x08"
ITERATIONS = 100000


def _get_hash_algorithm():
    """Return the hash algorithm used for key derivation."""
    return hashes.SHA256()


def _create_kdf(salt, iterations):
    """Create and return a PBKDF2HMAC instance."""
    return PBKDF2HMAC(
        algorithm=_get_hash_algorithm(),
        length=32,
        salt=salt,
        iterations=iterations,
    )


def derive_key(password: bytes) -> bytes:
    """Derive a 256-bit key from a password."""
    kdf = _create_kdf(SALT, ITERATIONS)
    return kdf.derive(password)


def verify_key(password: bytes, key: bytes) -> bool:
    """Verify that a password derives to the given key."""
    kdf = _create_kdf(SALT, ITERATIONS)
    try:
        kdf.verify(password, key)
        return True
    except Exception:
        return False
