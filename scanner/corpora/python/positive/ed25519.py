"""Ed25519 digital signature using the cryptography library."""
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey
)

private_key = Ed25519PrivateKey.generate()
public_key = private_key.public_key()
message = b"Message to sign"
signature = private_key.sign(message)
public_key.verify(signature, message)
print("Ed25519 signature verified")
