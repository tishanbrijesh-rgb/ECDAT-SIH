"""Regression tests for the stale scan cleanup utility."""
from datetime import datetime


def test_utc_now_returns_sqlite_compatible_datetime():
    """Cleanup timestamps stay naive UTC because SQLite drops timezone metadata."""
    # Import lazily so collection does not initialize the application database
    # before integration tests install their isolated DATABASE_URL.
    from scripts.cleanup_stale_scans import utc_now

    now = utc_now()

    assert isinstance(now, datetime)
    assert now.tzinfo is None
