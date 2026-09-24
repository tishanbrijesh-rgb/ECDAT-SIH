/** HMAC-SHA256 message authentication using Node.js crypto module. */
const crypto = require('crypto');

const key = crypto.randomBytes(32);
const message = 'important data to authenticate';

const hmac = crypto.createHmac('sha256', key);
hmac.update(message);
const digest = hmac.digest('hex');
console.log(`HMAC-SHA256: ${digest}`);
