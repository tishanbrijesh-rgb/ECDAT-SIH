"""AES-GCM encryption and decryption using PyCryptodome."""
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes

key = get_random_bytes(32)  # 256-bit key
cipher = AES.new(key, AES.MODE_GCM)
nonce = cipher.nonce
plaintext = b"Secret message for GCM mode"
ciphertext, tag = cipher.encrypt_and_digest(plaintext)

# Decrypt
cipher_dec = AES.new(key, AES.MODE_GCM, nonce=nonce)
decrypted = cipher_dec.decrypt_and_verify(ciphertext, tag)
print(decrypted)
