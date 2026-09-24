/** TLS connection using Node.js tls module. */
const tls = require('tls');

const options = {
    host: 'example.com',
    port: 443,
    rejectUnauthorized: true,
    ca: [fs.readFileSync('ca.pem')],
    servername: 'example.com',
};

const socket = tls.connect(options, () => {
    console.log(`TLS version: ${socket.getProtocol()}`);
    socket.write('GET / HTTP/1.1\r\nHost: example.com\r\n\r\n');
});

socket.on('data', (data) => {
    console.log(data.toString());
});
