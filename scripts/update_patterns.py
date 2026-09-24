"""Script to update crypto_patterns.json - fixes overly broad regex patterns."""
import json
import re

# Load current file (even if slightly corrupted, try to read it)
try:
    with open('scanner/rules/crypto_patterns.json', 'r', encoding='utf-8') as f:
        content = f.read()
    # Fix invalid escapes by doubling them
    content = re.sub(r'(?<!\)\(?!["\/bfnrtu])', r'\\', content)
    data = json.loads(content)
except (json.JSONDecodeError, FileNotFoundError):
    # Rebuild from scratch if needed
    data = {"algorithms": {}}

algo = data['algorithms']

# ---- SHA-256: remove overly broad EVP_MD_CTX / EVP_DigestInit / crypto.createHash ----
# These patterns match in ANY C file that uses OpenSSL EVP, regardless of algorithm
# causing SHA-256, SHA-512, MD5, SHA-1 false positives when only one hash is used
for sha_algo in ['SHA-256', 'SHA-512', 'SHA-1']:
    if sha_algo not in algo:
        continue
    pats = algo[sha_algo].get('patterns', [])
    # Remove generic EVP and createHash patterns
    pats = [p for p in pats if p not in (
        'EVP_MD_CTX', 'EVP_DigestInit',
        r'crypto\.createHash', r'crypto\.createHash\s*\('
    )]
    # Add specific SHA variant patterns for OpenSSL SHA functions
    if sha_algo == 'SHA-256':
        pats.extend(['SHA256_', 'SHA256_Init', 'SHA256_Update', 'SHA256_Final',
                      'SHA256_DIGEST_LENGTH'])
    elif sha_algo == 'SHA-512':
        pats.extend(['SHA512_', 'SHA512_Init', 'SHA512_Update', 'SHA512_Final',
                      'SHA512_DIGEST_LENGTH'])
    elif sha_algo == 'SHA-1':
        pats.extend(['SHA1_', 'SHA1_Init', 'SHA1_Update', 'SHA1_Final',
                      'SHA_DIGEST_LENGTH'])
    # Remove duplicates while preserving order
    seen = set()
    deduped = []
    for p in pats:
        if p not in seen:
            seen.add(p)
            deduped.append(p)
    algo[sha_algo]['patterns'] = deduped

# ---- MD5: remove generic crypto.createHash ----
if 'MD5' in algo:
    pats = algo['MD5'].get('patterns', [])
    pats = [p for p in pats if p not in (r'crypto\.createHash', r'crypto\.createHash\s*\(')]
    seen = set()
    deduped = []
    for p in pats:
        if p not in seen:
            seen.add(p)
            deduped.append(p)
    algo['MD5']['patterns'] = deduped

# ---- TLS: remove 'OpenSSL' provider name ----
# OpenSSL is a library, not a TLS protocol indicator
if 'TLS' in algo:
    pats = algo['TLS'].get('patterns', [])
    pats = [p for p in pats if p != 'OpenSSL']
    algo['TLS']['patterns'] = pats

# ---- AES: remove aead.Seal (generic AEAD, not AES-specific) ----
if 'AES' in algo:
    pats = algo['AES'].get('patterns', [])
    pats = [p for p in pats if p != r'aead\.Seal']
    algo['AES']['patterns'] = pats

# ---- RSA: remove generic subtle patterns ----
if 'RSA' in algo:
    pats = algo['RSA'].get('patterns', [])
    pats = [p for p in pats if p not in (
        r'crypto\.subtle\.sign', r'crypto\.subtle\.verify', r'crypto\.subtle\.generateKey'
    )]
    algo['RSA']['patterns'] = pats

# ---- HMAC: remove generic subtle patterns ----
if 'HMAC' in algo:
    pats = algo['HMAC'].get('patterns', [])
    pats = [p for p in pats if p not in (
        r'crypto\.subtle\.sign', r'crypto\.subtle\.verify', r'crypto\.subtle\.generateKey'
    )]
    algo['HMAC']['patterns'] = pats

# ---- ECDSA: remove generic subtle patterns ----
if 'ECDSA' in algo:
    pats = algo['ECDSA'].get('patterns', [])
    pats = [p for p in pats if p not in (
        r'crypto\.subtle\.sign', r'crypto\.subtle\.verify'
    )]
    algo['ECDSA']['patterns'] = pats

with open('scanner/rules/crypto_patterns.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2)

print('Patterns updated successfully')

# Verify
with open('scanner/rules/crypto_patterns.json', 'r', encoding='utf-8') as f:
    json.load(f)
print('JSON validation passed')
