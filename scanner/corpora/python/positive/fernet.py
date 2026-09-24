"""Fernet symmetric encryption using the cryptography library."""
from cryptography.fernet import Fernet

key = Fernet.generate_key()
cipher = Fernet(key)
plaintext = b"Secret message for Fernet"
token = cipher.encrypt(plaintext)
decrypted = cipher.decrypt(token)
print(decrypted)
