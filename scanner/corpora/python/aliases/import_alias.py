"""Import alias — the alias obscures the real crypto module name."""
from Crypto.Cipher import AES as aes_alias

def encrypt(data):
    key = b"\x00" * 16
    cipher = aes_alias.new(key, aes_alias.MODE_CBC, iv=b"\x00" * 16)
    return cipher.encrypt(data)

def decrypt(data):
    key = b"\x00" * 16
    cipher = aes_alias.new(key, aes_alias.MODE_CBC, iv=b"\x00" * 16)
    return cipher.decrypt(data)
