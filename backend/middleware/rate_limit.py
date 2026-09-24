"""Sliding-window rate limiter with per-endpoint rules (sync + async)."""
from __future__ import annotations

import functools
import hashlib
import inspect
import ipaddress
import math
import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from fastapi import HTTPException, Request

from backend.logging_config import get_logger

logger = get_logger("ecdat.rate_limit")

DEFAULT_THRESHOLD = 10
DEFAULT_WINDOW = 60
TRUSTED_PROXIES_ENV = "ECDAT_TRUSTED_PROXIES"


@dataclass(frozen=True)
class RateLimitRule:
    threshold: int
    window: int


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    retry_after: int = 0


class RateLimitStore(Protocol):
    """Atomic limiter storage contract for future shared-store implementations."""

    def check(
        self,
        rule_key: str,
        client_keys: tuple[str, ...],
        rule: RateLimitRule,
        now: float,
    ) -> RateLimitDecision: ...


# (rule_key, client_key) -> sorted monotonic timestamps
_windows: dict[tuple[str, str], list[float]] = {}
_lock = threading.Lock()


def _prune(now: float, window: int, rule_key: str | None = None) -> None:
    cutoff = now - window
    for key, timestamps in list(_windows.items()):
        if rule_key is not None and key[0] != rule_key:
            continue
        active = [timestamp for timestamp in timestamps if timestamp >= cutoff]
        if active:
            _windows[key] = active
        else:
            del _windows[key]


def _allow(rule_key: str, client_key: str, rule: RateLimitRule, now: float) -> bool:
    """Return True and record the hit, or False if over limit. Call under lock."""
    _prune(now, rule.window, rule_key)
    key = (rule_key, client_key)
    ts = _windows.get(key, [])
    ts = [t for t in ts if t >= now - rule.window]
    if len(ts) >= rule.threshold:
        _windows[key] = ts
        return False
    ts.append(now)
    _windows[key] = sorted(ts)
    return True


def _retry_after(
    rule_key: str,
    client_keys: tuple[str, ...],
    rule: RateLimitRule,
    now: float,
) -> int:
    waits = [
        timestamps[0] + rule.window - now
        for client_key in client_keys
        if len(timestamps := _windows.get((rule_key, client_key), [])) >= rule.threshold
    ]
    return max(1, math.ceil(max(waits, default=rule.window)))


class InMemoryRateLimitStore:
    """Thread-safe storage for one API process; not safe across replicas."""

    def check(
        self,
        rule_key: str,
        client_keys: tuple[str, ...],
        rule: RateLimitRule,
        now: float,
    ) -> RateLimitDecision:
        with _lock:
            allowed = all(_allow(rule_key, key, rule, now) for key in client_keys)
            retry_after = _retry_after(rule_key, client_keys, rule, now) if not allowed else 0
        return RateLimitDecision(allowed=allowed, retry_after=retry_after)


_in_memory_store = InMemoryRateLimitStore()


def _client_ip(request: Request, *_args: Any, **_kwargs: Any) -> str:
    peer = request.client.host if request.client else "unknown"
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded and _is_trusted_proxy(peer):
        forwarded_client = forwarded.split(",", 1)[0].strip()
        try:
            return str(ipaddress.ip_address(forwarded_client))
        except ValueError:
            logger.warning("Ignoring invalid X-Forwarded-For client address")
    return peer


def _client_key(request: Request, *_args: Any, **_kwargs: Any) -> str:
    if os.getenv("ECDAT_ALLOW_ROLE_HEADER", "").strip().lower() == "true":
        demo_role = request.headers.get("x-ecdat-role")
        if demo_role:
            digest = hashlib.sha256(demo_role.strip().casefold().encode("utf-8")).hexdigest()
            return f"demo-role:{digest}"
    return _client_ip(request)


def _is_trusted_proxy(peer: str) -> bool:
    configured = os.getenv(TRUSTED_PROXIES_ENV, "")
    if not configured.strip():
        return False
    try:
        address = ipaddress.ip_address(peer)
        networks = [
            ipaddress.ip_network(value.strip(), strict=False)
            for value in configured.split(",")
            if value.strip()
        ]
    except ValueError:
        return False
    return any(address in network for network in networks)


def limit(
    threshold: int | None = None,
    window: int = DEFAULT_WINDOW,
    *,
    key_fn: Callable[..., str | tuple[str, ...]] | None = None,
    store: RateLimitStore | None = None,
) -> Callable:
    """Decorator: apply sliding-window rate limiting to a FastAPI endpoint.

    Works with both sync and async endpoint functions.

    Args:
        threshold: Max requests per window. Reads ECDAT_RATE_LIMIT if omitted.
        window: Window size in seconds.
        key_fn: Identity function returning one or more independent grouping keys.
        store: Atomic storage implementation (default: process-local in-memory store).
    """
    max_req = threshold if threshold is not None else int(
        os.getenv("ECDAT_RATE_LIMIT", str(DEFAULT_THRESHOLD))
    )
    if max_req <= 0:
        raise ValueError("Rate-limit threshold must be a positive integer")
    if window <= 0:
        raise ValueError("Rate-limit window must be a positive integer")
    identity = key_fn or _client_key
    selected_store = store or _in_memory_store

    def decorator(func: Callable) -> Callable:
        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(request: Request, *args: Any, **kwargs: Any) -> Any:
                if not isinstance(request, Request):
                    return await func(None, request, *args, **kwargs)
                return await _check_and_call(
                    func, request, args, kwargs, max_req, window, identity, selected_store
                )

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(request: Request, *args: Any, **kwargs: Any) -> Any:
                if not isinstance(request, Request):
                    return func(None, request, *args, **kwargs)
                return _check_and_call(
                    func, request, args, kwargs, max_req, window, identity, selected_store
                )

            return sync_wrapper

    return decorator


def _check_and_call(
    func: Callable,
    request: Request,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    max_req: int,
    window: int,
    identity: Callable[..., str | tuple[str, ...]],
    store: RateLimitStore,
) -> Any:
    """Check rate limit, call the function or raise 429."""
    rule = RateLimitRule(threshold=max_req, window=window)
    identity_keys = identity(request, *args, **kwargs)
    keys = (identity_keys,) if isinstance(identity_keys, str) else identity_keys
    now = time.monotonic()

    decision = store.check(func.__name__, keys, rule, now)

    if not decision.allowed:
        request_id = request.headers.get("x-request-id", "-")
        logger.warning(
            "Rate limit exceeded",
            extra={"extra_data": {"path": request.url.path, "client": keys[0]}},
        )
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please retry later.",
            headers={"Retry-After": str(decision.retry_after), "X-Request-ID": request_id},
        )

    return func(request, *args, **kwargs)
