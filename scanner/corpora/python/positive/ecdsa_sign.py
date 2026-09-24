"""ECDSA digital signature using PyCryptodome."""
from Crypto.PublicKey import ECC
from Crypto.Signature import DSS
from Crypto.Hash import SHA256

private_key = ECC.generate(curve="P-256")
public_key = private_key.public_key()
message = b"Message to sign"
h = SHA256.new(message)
signer = DSS.new(private_key, "fips-186-3")
signature = signer.sign(h)

# Verify
verifier = DSS.new(public_key, "fips-186-3")
try:
    verifier.verify(h, signature)
    print("Signature valid")
except ValueError:
    print("Signature invalid")
