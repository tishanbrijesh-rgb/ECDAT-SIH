import hashlib

from Crypto.Cipher import AES
from cryptography.hazmat.primitives.asymmetric import ec, rsa


def mixed_operations(key: bytes, payload: bytes) -> None:
    hashlib.md5(payload).digest()
    hashlib.sha1(payload).digest()
    AES.new(key, AES.MODE_GCM)
    rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ec.generate_private_key(ec.SECP256R1())
