"""Regression tests for the stale scan-job cleanup utility."""
from datetime import datetime, timedelta


def test_utc_now_returns_sqlite_compatible_datetime():
    """Cleanup timestamps are timezone-aware UTC, consistent with model defaults.

    The utc_now() helper returns aware UTC so duration arithmetic is correct.
    """
    from scripts.cleanup_stale_scans import utc_now

    now = utc_now()

    assert isinstance(now, datetime)
    assert now.tzinfo is not None
    # Verify it is actually UTC, not some other timezone.
    assert now.tzinfo.utcoffset(now) == timedelta(0)
