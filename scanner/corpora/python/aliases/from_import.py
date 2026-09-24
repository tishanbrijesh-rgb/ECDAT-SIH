"""From-import usage — imported names used directly without module prefix."""
from Crypto.Cipher import AES
from hashlib import sha256
import hmac

def encrypt_data(data, key):
    cipher = AES.new(key, AES.MODE_ECB)
    return cipher.encrypt(data)

def compute_hash(data):
    return sha256(data).hexdigest()

def sign_message(key, msg):
    return hmac.new(key, msg, sha256).hexdigest()
