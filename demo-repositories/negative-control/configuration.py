"""Documentation mentions AES, RSA and ECDSA but performs no cryptography."""

ECDSA = object()
DISPLAY_LABEL = "AES-256-GCM"
HELP_TEXT = "Migrate RSA keys after review"


def describe() -> str:
    return "SHA-256 is listed for documentation only"
