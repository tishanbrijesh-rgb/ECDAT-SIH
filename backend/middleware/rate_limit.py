"""Sliding-window rate limiter with per-endpoint rules (sync + async)."""
from __future__ import annotations

import functools
import hashlib
import inspect
import os
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable

from fastapi import HTTPException, Request

from backend.logging_config import get_logger

logger = get_logger("ecdat.rate_limit")

DEFAULT_THRESHOLD = 10
DEFAULT_WINDOW = 60


@dataclass(frozen=True)
class _Hit:
    timestamp: float


@dataclass
class _Rule:
    threshold: int
    window: int


# (rule_key, client_key) -> sorted monotonic timestamps
_windows: dict[tuple[str, str], list[float]] = {}
_lock = threading.Lock()


def _prune(now: float, window: int) -> None:
    cutoff = now - window
    stale = [k for k, ts in _windows.items() if ts and ts[0] < cutoff]
    for k in stale:
        del _windows[k]


def _allow(rule_key: str, client_key: str, rule: _Rule, now: float) -> bool:
    """Return True and record the hit, or False if over limit. Call under lock."""
    _prune(now, rule.window)
    key = (rule_key, client_key)
    ts = _windows.get(key, [])
    ts = [t for t in ts if t >= now - rule.window]
    if len(ts) >= rule.threshold:
        _windows[key] = ts
        return False
    ts.append(now)
    _windows[key] = sorted(ts)
    return True


def _client_ip(request: Request) -> str:
    principal = request.headers.get("authorization") or request.headers.get("x-ecdat-role")
    if principal:
        return "principal:" + hashlib.sha256(principal.encode("utf-8")).hexdigest()
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def limit(
    threshold: int | None = None,
    window: int = DEFAULT_WINDOW,
    *,
    key_fn: Callable[[Request], str] | None = None,
) -> Callable:
    """Decorator: apply sliding-window rate limiting to a FastAPI endpoint.

    Works with both sync and async endpoint functions.

    Args:
        threshold: Max requests per window. Reads ECDAT_RATE_LIMIT if omitted.
        window: Window size in seconds.
        key_fn: Identity function for rate-limit grouping (default: client IP).
    """
    max_req = threshold if threshold is not None else int(
        os.getenv("ECDAT_RATE_LIMIT", str(DEFAULT_THRESHOLD))
    )
    identity = key_fn or _client_ip

    def decorator(func: Callable) -> Callable:
        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(request: Request, *args: Any, **kwargs: Any) -> Any:
                if not isinstance(request, Request):
                    return await func(None, request, *args, **kwargs)
                return await _check_and_call(func, request, args, kwargs, max_req, window, identity)

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(request: Request, *args: Any, **kwargs: Any) -> Any:
                if not isinstance(request, Request):
                    return func(None, request, *args, **kwargs)
                return _check_and_call(func, request, args, kwargs, max_req, window, identity)

            return sync_wrapper

    return decorator


def _check_and_call(
    func: Callable,
    request: Request,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    max_req: int,
    window: int,
    identity: Callable[[Request], str],
) -> Any:
    """Check rate limit, call the function or raise 429."""
    rule = _Rule(threshold=max_req, window=window)
    key = identity(request)
    now = time.monotonic()

    with _lock:
        allowed = _allow(func.__name__, key, rule, now)

    if not allowed:
        request_id = request.headers.get("x-request-id", "-")
        logger.warning(
            "Rate limit exceeded",
            extra={"extra_data": {"path": request.url.path, "client": key}},
        )
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please retry later.",
            headers={"Retry-After": str(window), "X-Request-ID": request_id},
        )

    return func(request, *args, **kwargs)
