"""Security contracts for distributed authentication rate limiting."""

import asyncio
from types import SimpleNamespace

import pytest

from app.services.auth_rate_limiter import (
    AuthRateLimitAction,
    AuthRateLimitExceeded,
    AuthRateLimiter,
    AuthRateLimiterUnavailable,
)


class _ScriptedRedis:
    def __init__(self, results):
        self.results = iter(results)
        self.calls = []

    async def eval(self, *args):
        self.calls.append(args)
        return next(self.results)


class _ClientProvider:
    def __init__(self, client):
        self.client = client

    async def get_client(self):
        return self.client


def _settings(*, source_limit=1, email_limit=1, fail_open=False):
    values = {
        "auth_rate_limit_window_seconds": 60,
        "auth_rate_limit_fail_open": fail_open,
    }
    for action in AuthRateLimitAction:
        prefix = f"auth_rate_limit_{action.value}"
        values[f"{prefix}_source"] = source_limit
        values[f"{prefix}_email"] = email_limit
    return SimpleNamespace(**values)


@pytest.mark.parametrize("action", list(AuthRateLimitAction))
def test_each_auth_action_rejects_an_attempt_over_the_configured_limit(action):
    redis = _ScriptedRedis(
        [
            [1, 1, 59, 59],
            [2, 2, 58, 58],
        ]
    )
    limiter = AuthRateLimiter(_ClientProvider(redis), _settings())

    first = asyncio.run(
        limiter.enforce(
            action,
            source="203.0.113.8",
            email="  User@Example.COM ",
        )
    )

    assert first.allowed is True
    with pytest.raises(AuthRateLimitExceeded) as raised:
        asyncio.run(
            limiter.enforce(
                action,
                source="203.0.113.8",
                email="user@example.com",
            )
        )
    assert raised.value.decision.allowed is False
    assert raised.value.decision.retry_after_seconds == 58


def test_rate_limit_keys_partition_source_and_normalized_email_without_pii():
    redis = _ScriptedRedis([[1, 1, 59, 59], [1, 2, 59, 58]])
    limiter = AuthRateLimiter(_ClientProvider(redis), _settings(email_limit=1))

    asyncio.run(
        limiter.check(
            AuthRateLimitAction.LOGIN,
            source="198.51.100.1",
            email=" Trader@Example.COM ",
        )
    )
    decision = asyncio.run(
        limiter.check(
            AuthRateLimitAction.LOGIN,
            source="198.51.100.2",
            email="trader@example.com",
        )
    )

    first_source_key, first_email_key = redis.calls[0][2:4]
    second_source_key, second_email_key = redis.calls[1][2:4]
    assert first_source_key != second_source_key
    assert first_email_key == second_email_key
    assert "trader@example.com" not in first_email_key
    assert "198.51.100" not in first_source_key
    assert decision.allowed is False
    assert decision.source_remaining == 0
    assert decision.email_remaining == 0


@pytest.mark.parametrize("fail_open", [False, True])
def test_rate_limit_backend_failure_obeys_explicit_availability_policy(fail_open):
    class _UnavailableProvider:
        async def get_client(self):
            raise OSError("redis unavailable")

    limiter = AuthRateLimiter(
        _UnavailableProvider(),
        _settings(fail_open=fail_open),
    )

    if fail_open:
        decision = asyncio.run(
            limiter.check(
                AuthRateLimitAction.LOGIN,
                source="203.0.113.9",
                email="user@example.com",
            )
        )
        assert decision.allowed is True
        assert decision.backend_available is False
        assert decision.retry_after_seconds == 0
    else:
        with pytest.raises(AuthRateLimiterUnavailable):
            asyncio.run(
                limiter.check(
                    AuthRateLimitAction.LOGIN,
                    source="203.0.113.9",
                    email="user@example.com",
                )
            )
