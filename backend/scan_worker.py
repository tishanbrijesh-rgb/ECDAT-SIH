"""Isolated scanner subprocess. It never receives control-plane credentials."""
import json
import os
import sys
import time
from pathlib import Path

from backend.services.scanner_runner import collect_scan_result
from scanner.limits import positive_int


def _json_safe(value):
    """Normalize collector output into bounded JSON-compatible primitives."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return str(value)


def _publish_progress(progress_path: Path, progress: dict) -> bool:
    """Atomically publish bounded telemetry without allowing it to abort a scan."""
    encoded = json.dumps(
        progress, ensure_ascii=False, separators=(",", ":"),
    ).encode("utf-8")
    if len(encoded) > 64 * 1024:
        return False
    temporary_path = progress_path.with_name(
        f".{progress_path.name}.{os.getpid()}.tmp"
    )
    try:
        temporary_path.write_bytes(encoded)
        for attempt in range(3):
            try:
                os.replace(temporary_path, progress_path)
                return True
            except PermissionError:
                if attempt < 2:
                    time.sleep(0.01 * (attempt + 1))
        return False
    except OSError:
        return False
    finally:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass

if __name__ == '__main__':
    repo_path = sys.argv[1]
    output_path = Path(sys.argv[2])
    progress_path = Path(sys.argv[3]) if len(sys.argv) > 3 else None

    def publish_progress(progress: dict) -> None:
        if progress_path is None:
            return
        _publish_progress(progress_path, progress)

    result = _json_safe(collect_scan_result(repo_path, progress_callback=publish_progress))
    encoded = json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    limit = positive_int(
        "ECDAT_MAX_WORKER_RESULT_BYTES",
        32 * 1024 * 1024,
        128 * 1024 * 1024,
    )
    if len(encoded) > limit:
        raise SystemExit("Scan result exceeds the configured worker artifact limit")
    temporary_path = output_path.with_suffix(".tmp")
    temporary_path.write_bytes(encoded)
    os.replace(temporary_path, output_path)
