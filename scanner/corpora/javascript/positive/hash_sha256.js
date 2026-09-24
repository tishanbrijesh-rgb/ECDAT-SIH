/** SHA-256 hashing using Node.js crypto module. */
const crypto = require('crypto');

function sha256(data) {
    return crypto.createHash('sha256').update(data).digest('hex');
}

function sha256Sync(data) {
    const hash = crypto.createHash('sha256');
    hash.update(data);
    return hash.digest('hex');
}

const data = 'data to hash';
console.log(sha256(data));
