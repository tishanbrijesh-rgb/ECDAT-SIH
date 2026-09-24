"""ChaCha20-Poly1305 encryption using the cryptography library."""
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

key = bytes(range(32))  # 256-bit key
nonce = bytes(range(12))  # 96-bit nonce
cipher = ChaCha20Poly1305(key)
plaintext = b"Secret message for ChaCha20"
aad = b"associated authenticated data"
ciphertext = cipher.encrypt(nonce, plaintext, aad)
decrypted = cipher.decrypt(nonce, ciphertext, aad)
print(decrypted)
