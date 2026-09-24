"""Focused regression tests for the in-process rate limiter."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import HTTPException, Request

from backend.middleware import rate_limit


@pytest.fixture(autouse=True)
def clear_rate_limit_windows():
    with rate_limit._lock:
        rate_limit._windows.clear()
    yield
    with rate_limit._lock:
        rate_limit._windows.clear()


def test_prune_preserves_hits_inside_the_rolling_window() -> None:
    key = ("login", "client")
    rate_limit._windows[key] = [0.0, 59.0]

    rate_limit._prune(now=61.0, window=60)

    assert rate_limit._windows[key] == [59.0]


def test_threshold_two_rejects_third_hit_in_every_rolling_minute() -> None:
    rule = rate_limit.RateLimitRule(threshold=2, window=60)

    decisions = [
        rate_limit._allow("login", "client", rule, now)
        for now in (0.0, 59.0, 61.0, 61.1)
    ]

    assert decisions == [True, True, True, False]


def test_forwarded_header_is_ignored_without_a_trusted_proxy(monkeypatch) -> None:
    monkeypatch.delenv("ECDAT_TRUSTED_PROXIES", raising=False)
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(b"x-forwarded-for", b"203.0.113.9")],
            "client": ("198.51.100.7", 41000),
        }
    )

    assert rate_limit._client_ip(request) == "198.51.100.7"


def test_forwarded_header_is_used_when_socket_peer_is_in_trusted_cidr(monkeypatch) -> None:
    monkeypatch.setenv("ECDAT_TRUSTED_PROXIES", "192.0.2.0/24")
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(b"x-forwarded-for", b"203.0.113.9")],
            "client": ("192.0.2.7", 41000),
        }
    )

    assert rate_limit._client_ip(request) == "203.0.113.9"


def test_explicit_demo_role_header_mode_partitions_non_login_limits(monkeypatch) -> None:
    monkeypatch.setenv("ECDAT_ALLOW_ROLE_HEADER", "true")
    viewer = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/scan",
            "headers": [(b"x-ecdat-role", b"viewer")],
            "client": ("198.51.100.7", 41000),
        }
    )
    analyst = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/scan",
            "headers": [(b"x-ecdat-role", b"security_analyst")],
            "client": ("198.51.100.7", 41000),
        }
    )

    assert rate_limit._client_key(viewer) != rate_limit._client_key(analyst)


def test_limit_rejects_non_positive_threshold() -> None:
    with pytest.raises(ValueError, match="threshold"):
        rate_limit.limit(threshold=0)


def test_limit_rejects_non_positive_window() -> None:
    with pytest.raises(ValueError, match="window"):
        rate_limit.limit(window=0)


def test_login_identity_has_independent_client_and_normalized_username_keys() -> None:
    from backend.routers.auth import LoginRequest, _login_rate_limit_keys

    first = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/auth/login",
            "headers": [],
            "client": ("198.51.100.1", 41000),
        }
    )
    second = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/auth/login",
            "headers": [],
            "client": ("198.51.100.2", 41001),
        }
    )

    first_keys = _login_rate_limit_keys(first, LoginRequest(username=" Alice ", password="secret"))
    second_keys = _login_rate_limit_keys(second, LoginRequest(username="alice", password="secret"))

    assert first_keys[0] != second_keys[0]
    assert first_keys[1] == second_keys[1] == "username:alice"


def test_username_bucket_blocks_login_after_client_address_rotation() -> None:
    from backend.routers.auth import LoginRequest, _login_rate_limit_keys

    @rate_limit.limit(threshold=1, key_fn=_login_rate_limit_keys)
    def endpoint(request: Request, payload: LoginRequest) -> None:
        return None

    first = Request(
        {"type": "http", "method": "POST", "path": "/", "headers": [], "client": ("198.51.100.1", 1)}
    )
    second = Request(
        {"type": "http", "method": "POST", "path": "/", "headers": [], "client": ("198.51.100.2", 2)}
    )
    payload = LoginRequest(username="alice", password="secret")

    endpoint(first, payload)
    with pytest.raises(HTTPException) as error:
        endpoint(second, payload)

    assert error.value.status_code == 429


def test_rejection_reports_remaining_rolling_window_delay(monkeypatch) -> None:
    moments = iter((0.0, 59.0, 59.5))
    monkeypatch.setattr(rate_limit.time, "monotonic", lambda: next(moments))

    @rate_limit.limit(threshold=2, window=60)
    def endpoint(request: Request) -> None:
        return None

    request = Request(
        {"type": "http", "method": "GET", "path": "/", "headers": [], "client": ("198.51.100.1", 1)}
    )
    endpoint(request)
    endpoint(request)

    with pytest.raises(HTTPException) as error:
        endpoint(request)

    assert error.value.status_code == 429
    assert error.value.headers == {"Retry-After": "1", "X-Request-ID": "-"}


def test_limit_accepts_an_injectable_shared_store_contract() -> None:
    class RejectingStore:
        def check(self, rule_key, client_keys, rule, now):
            return rate_limit.RateLimitDecision(allowed=False, retry_after=7)

    @rate_limit.limit(threshold=2, store=RejectingStore())
    def endpoint(request: Request) -> None:
        return None

    request = Request(
        {"type": "http", "method": "GET", "path": "/", "headers": [], "client": ("198.51.100.1", 1)}
    )

    with pytest.raises(HTTPException) as error:
        endpoint(request)

    assert error.value.headers["Retry-After"] == "7"


def test_short_window_check_does_not_prune_a_long_window_bucket() -> None:
    long_key = ("long_operation", "client")
    rate_limit._windows[long_key] = [100.0]

    rate_limit._allow(
        "short_operation",
        "client",
        rate_limit.RateLimitRule(threshold=2, window=60),
        now=200.0,
    )

    assert rate_limit._windows[long_key] == [100.0]


def test_concurrent_checks_do_not_lose_increments() -> None:
    store = rate_limit.InMemoryRateLimitStore()
    rule = rate_limit.RateLimitRule(threshold=25, window=60)

    with ThreadPoolExecutor(max_workers=16) as executor:
        decisions = list(
            executor.map(
                lambda _: store.check("endpoint", ("client",), rule, now=100.0),
                range(100),
            )
        )

    assert sum(decision.allowed for decision in decisions) == 25
    assert len(rate_limit._windows[("endpoint", "client")]) == 25
