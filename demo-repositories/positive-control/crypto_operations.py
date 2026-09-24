import hashlib
import hmac

from Crypto.Cipher import AES
from cryptography.hazmat.primitives.asymmetric import ec, rsa


def operations(key: bytes, payload: bytes) -> None:
    hashlib.sha256(payload).digest()
    hmac.new(key, payload, hashlib.sha256).digest()
    AES.new(key, AES.MODE_GCM)
    rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ec.generate_private_key(ec.SECP256R1())
