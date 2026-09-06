"""Internal subprocess entry point. Never executes scanned repository code."""
import sys
from backend.db import engine
from backend.services.scanner_runner import run_scan

if __name__ == '__main__':
    try:
        result = run_scan(sys.argv[1], int(sys.argv[2]))
        raise SystemExit(0 if result['status'] == 'completed' else 1)
    finally:
        engine.dispose()
