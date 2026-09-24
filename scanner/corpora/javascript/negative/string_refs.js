/** Module with only string references to algorithms, no real crypto. */

// Configuration
const CONFIG = {
    encryption: "AES-256-GCM",
    hash: "SHA-256",
    signature: "ECDSA-P256",
    keyExchange: "RSA-4096"
};

// Documentation strings
const DOCS = `
This project uses:
- aes_gcm for symmetric encryption
- sha256 for hashing
- rsa_oaep for key transport
- hmac for message authentication
`;

function getAlgorithm(name) {
    const map = {
        encrypt: "AES-GCM",
        hash: "SHA-256",
        sign: "ECDSA",
    };
    return map[name] || "unknown";
}
