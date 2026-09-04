"""Conservative removal of free-form source content from exported evidence."""
import re

RAW_FIELDS = {"snippet", "arg", "raw_line", "content", "password", "secret", "token", "private_key"}


def redact_evidence(value):
    if isinstance(value, dict):
        return {key: "[REDACTED]" if str(key).lower() in RAW_FIELDS else redact_evidence(item)
                for key, item in value.items()}
    if isinstance(value, list):
        return [redact_evidence(item) for item in value]
    if isinstance(value, str) and ("PRIVATE KEY-----" in value or
            re.search(r"(?i)(password|secret|token|api_key)\s*[:=]", value)):
        return "[REDACTED]"
    return value
