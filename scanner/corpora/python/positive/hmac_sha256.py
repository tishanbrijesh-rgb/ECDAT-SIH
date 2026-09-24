"""HMAC-SHA256 message authentication using Python hashlib."""
import hmac
import hashlib

key = b"my-secret-key"
message = b"important data to authenticate"
digest = hmac.new(key, message, hashlib.sha256).hexdigest()
print(f"HMAC-SHA256: {digest}")
