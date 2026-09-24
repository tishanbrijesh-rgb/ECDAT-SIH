/** RSA key generation using Node.js crypto module. */
const crypto = require('crypto');

const { publicKey, privateKey } = crypto.generateKeyPairSync('rsa', {
    modulusLength: 4096,
    publicKeyEncoding: { type: 'spki', format: 'pem' },
    privateKeyEncoding: { type: 'pkcs8', format: 'pem' },
});

const data = Buffer.from('data to encrypt');
const encrypted = crypto.publicEncrypt(publicKey, data);
const decrypted = crypto.privateDecrypt(privateKey, encrypted);
console.log(decrypted.toString());
