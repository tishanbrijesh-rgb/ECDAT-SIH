"""AES-CBC encryption and decryption using PyCryptodome."""
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from Crypto.Random import get_random_bytes

key = get_random_bytes(16)  # 128-bit key
iv = get_random_bytes(16)
cipher = AES.new(key, AES.MODE_CBC, iv)
padded_data = pad(b"Secret message for CBC mode", AES.block_size)
ciphertext = cipher.encrypt(padded_data)

# Decrypt
cipher_dec = AES.new(key, AES.MODE_CBC, iv)
decrypted_padded = cipher_dec.decrypt(ciphertext)
decrypted = unpad(decrypted_padded, AES.block_size)
print(decrypted)
