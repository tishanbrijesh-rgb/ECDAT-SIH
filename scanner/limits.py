"""Bound local reads; these limits are not a filesystem security sandbox."""
import os
import stat


def positive_int(name: str, default: int, maximum: int) -> int:
    value = int(os.getenv(name, str(default)))
    if value < 1 or value > maximum:
        raise ValueError(f"Invalid {name}")
    return value


def max_file_bytes() -> int:
    return positive_int('ECDAT_MAX_FILE_BYTES', 8 * 1024 * 1024, 128 * 1024 * 1024)


def max_evidence_count() -> int:
    """Bound aggregate evidence retained before correlation and persistence."""
    return positive_int('ECDAT_MAX_EVIDENCE', 100000, 1000000)


def read_bytes(path: str) -> bytes:
    limit = max_file_bytes()
    if os.path.islink(path):
        raise OSError('Linked files are outside scan scope')
    with open(path, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise OSError('Unsupported or oversized scan file')
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise OSError('Scan file grew beyond configured limit')
    return data


def read_text(path: str, errors='strict') -> str:
    return read_bytes(path).decode('utf-8', errors=errors)
