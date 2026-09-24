"""File containing only string literals, no real crypto operations."""

CONFIG = {
    "encryption_algorithm": "AES-256-GCM",
    "hash_function": "SHA-256",
    "signature_scheme": "ECDSA-P256",
}

README = """
This project uses AES for encryption.
Hash function: SHA-256.
Key exchange: RSA-4096.
"""

def get_algorithm_info() -> str:
    return "We plan to use ChaCha20 for streaming encryption."
