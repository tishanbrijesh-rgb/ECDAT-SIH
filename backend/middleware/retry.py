"""Retry decorator with exponential backoff for transient database errors.

Catches ``SQLAlchemyError`` (specifically ``OperationalError`` for SQLite lock
contention) and retries up to 3 times with jittered exponential backoff.
"""
from __future__ import annotations

import asyncio
import functools
import os
import random
from collections.abc import Callable
from typing import Any, TypeVar

from sqlalchemy.exc import OperationalError, SQLAlchemyError

from backend.logging_config import get_logger

logger = get_logger("ecdat.retry")

F = TypeVar("F", bound=Callable[..., Any])

_DEFAULT_MAX_RETRIES = 3
_DEFAULT_BASE_DELAY = float(os.getenv("ECDAT_RETRY_BASE_DELAY", "0.1"))
_DEFAULT_MAX_DELAY = float(os.getenv("ECDAT_RETRY_MAX_DELAY", "5.0"))


def retry_db(
    max_retries: int = _DEFAULT_MAX_RETRIES,
    base_delay: float = _DEFAULT_BASE_DELAY,
    max_delay: float = _DEFAULT_MAX_DELAY,
) -> Callable[[F], F]:
    """Decorator: retry a sync or async function on transient ``SQLAlchemyError``.

    Args:
        max_retries: Maximum retry attempts after the first failure.
        base_delay: Initial backoff delay in seconds.
        max_delay: Upper bound on backoff delay in seconds.

    Returns:
        Wrapped function with identical signature.
    """
    if max_retries < 1:
        raise ValueError("max_retries must be >= 1")

    def decorator(func: F) -> F:
        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                last_exc: BaseException | None = None
                for attempt in range(max_retries + 1):
                    try:
                        return await func(*args, **kwargs)  # type: ignore[return-value]
                    except OperationalError as exc:
                        last_exc = exc
                        _log_retry(func, attempt, max_retries, exc)
                        if attempt < max_retries:
                            await _sleep(attempt, base_delay, max_delay)
                    except SQLAlchemyError as exc:
                        last_exc = exc
                        _log_retry(func, attempt, max_retries, exc)
                        if attempt < max_retries:
                            await _sleep(attempt, base_delay, max_delay)
                assert last_exc is not None
                raise last_exc

            return async_wrapper  # type: ignore[return-value]
        else:

            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                last_exc: BaseException | None = None
                for attempt in range(max_retries + 1):
                    try:
                        return func(*args, **kwargs)  # type: ignore[return-value]
                    except OperationalError as exc:
                        last_exc = exc
                        _log_retry(func, attempt, max_retries, exc)
                        if attempt < max_retries:
                            _sleep_sync(attempt, base_delay, max_delay)
                    except SQLAlchemyError as exc:
                        last_exc = exc
                        _log_retry(func, attempt, max_retries, exc)
                        if attempt < max_retries:
                            _sleep_sync(attempt, base_delay, max_delay)
                assert last_exc is not None
                raise last_exc

            return sync_wrapper  # type: ignore[return-value]

    return decorator


async def _sleep(attempt: int, base_delay: float, max_delay: float) -> None:
    """Async sleep with exponential backoff + full jitter."""
    delay = min(base_delay * (2 ** attempt), max_delay)
    jittered = random.uniform(0, delay)
    logger.debug("Retry backoff: %.3fs (attempt %d)", jittered, attempt + 1)
    await asyncio.sleep(jittered)


def _sleep_sync(attempt: int, base_delay: float, max_delay: float) -> None:
    """Sync sleep with exponential backoff + full jitter."""
    delay = min(base_delay * (2 ** attempt), max_delay)
    jittered = random.uniform(0, delay)
    logger.debug("Retry backoff: %.3fs (attempt %d)", jittered, attempt + 1)
    import time as _time
    _time.sleep(jittered)


def _log_retry(func: Callable[..., Any], attempt: int, max_retries: int,
               exc: BaseException) -> None:
    logger.warning(
        "Transient DB error in %s — attempt %d/%d: %s",
        func.__name__, attempt + 1, max_retries + 1, exc,
    )
