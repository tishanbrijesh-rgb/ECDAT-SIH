"""TLS/SSL context creation and usage in Python."""
import ssl
import socket

context = ssl.create_default_context()
context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
context.load_verify_locations(cafile="/path/to/ca.pem")
context.check_hostname = True
context.verify_mode = ssl.CERT_REQUIRED

hostname = "example.com"
with socket.create_connection((hostname, 443)) as sock:
    with context.wrap_socket(sock, server_hostname=hostname) as ssock:
        print(f"TLS version: {ssock.version()}")
