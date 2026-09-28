"""Distributed rate limiting for unauthenticated account operations.

Every attempt consumes two counters in one Redis transaction: one for the
request source and one for the canonical email address.  Identifiers are
SHA-256 digests in Redis keys so operational key inspection does not disclose
emails or source addresses.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum

from redis.exceptions import RedisError

from app.core.config import Settings, settings
from app.core.redis import RedisClient, redis_client
from app.models.user import normalize_email


class AuthRateLimitAction(str, Enum):
    REGISTRATION = "registration"
    LOGIN = "login"
    VERIFICATION_RESEND = "verification_resend"
    RECOVERY = "recovery"


@dataclass(frozen=True)
class AuthRateLimitPolicy:
    window_seconds: int
    source_limit: int
    email_limit: int


@dataclass(frozen=True)
class AuthRateLimitDecision:
    allowed: bool
    retry_after_seconds: int
    source_remaining: int
    email_remaining: int
    backend_available: bool = True


class AuthRateLimitExceeded(Exception):
    """Raised by :meth:`AuthRateLimiter.enforce` when an attempt is rejected."""

    def __init__(self, decision: AuthRateLimitDecision) -> None:
        self.decision = decision
        super().__init__("authentication attempt rate limit exceeded")


class AuthRateLimiterUnavailable(Exception):
    """Raised when Redis is unavailable and fail-open is disabled."""


# Increment and expire both buckets atomically.  Continuing to increment both
# counters after one exceeds its limit prevents attackers from rotating only
# one dimension while keeping the other artificially below its threshold.
_CONSUME_SCRIPT = """
local source_count = redis.call('INCR', KEYS[1])
if source_count == 1 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
end

local email_count = redis.call('INCR', KEYS[2])
if email_count == 1 then
  redis.call('EXPIRE', KEYS[2], ARGV[1])
end

local source_ttl = redis.call('TTL', KEYS[1])
local email_ttl = redis.call('TTL', KEYS[2])
return {source_count, email_count, source_ttl, email_ttl}
"""


class AuthRateLimiter:
    """Consume and enforce configurable per-action authentication limits."""

    def __init__(
        self,
        client_provider: RedisClient = redis_client,
        app_settings: Settings = settings,
    ) -> None:
        self._client_provider = client_provider
        self._settings = app_settings

    def policy_for(self, action: AuthRateLimitAction | str) -> AuthRateLimitPolicy:
        action = AuthRateLimitAction(action)
        prefix = f"auth_rate_limit_{action.value}"
        return AuthRateLimitPolicy(
            window_seconds=self._settings.auth_rate_limit_window_seconds,
            source_limit=getattr(self._settings, f"{prefix}_source"),
            email_limit=getattr(self._settings, f"{prefix}_email"),
        )

    async def check(
        self,
        action: AuthRateLimitAction | str,
        *,
        source: str,
        email: str,
    ) -> AuthRateLimitDecision:
        """Consume one attempt and return whether both buckets remain allowed."""
        parsed_action = AuthRateLimitAction(action)
        policy = self.policy_for(parsed_action)
        source_key, email_key = self._keys(parsed_action, source, email)

        try:
            client = await self._client_provider.get_client()
            raw_result = await client.eval(
                _CONSUME_SCRIPT,
                2,
                source_key,
                email_key,
                policy.window_seconds,
            )
            source_count, email_count, source_ttl, email_ttl = (
                int(value) for value in raw_result
            )
        except (RedisError, OSError) as exc:
            if self._settings.auth_rate_limit_fail_open:
                return AuthRateLimitDecision(
                    allowed=True,
                    retry_after_seconds=0,
                    source_remaining=policy.source_limit,
                    email_remaining=policy.email_limit,
                    backend_available=False,
                )
            raise AuthRateLimiterUnavailable(
                "authentication rate-limit backend is unavailable"
            ) from exc

        source_exceeded = source_count > policy.source_limit
        email_exceeded = email_count > policy.email_limit
        retry_after = max(
            source_ttl if source_exceeded and source_ttl > 0 else 0,
            email_ttl if email_exceeded and email_ttl > 0 else 0,
        )
        return AuthRateLimitDecision(
            allowed=not (source_exceeded or email_exceeded),
            retry_after_seconds=retry_after,
            source_remaining=max(0, policy.source_limit - source_count),
            email_remaining=max(0, policy.email_limit - email_count),
        )

    async def enforce(
        self,
        action: AuthRateLimitAction | str,
        *,
        source: str,
        email: str,
    ) -> AuthRateLimitDecision:
        """Consume an attempt or raise :class:`AuthRateLimitExceeded`."""
        decision = await self.check(action, source=source, email=email)
        if not decision.allowed:
            raise AuthRateLimitExceeded(decision)
        return decision

    @staticmethod
    def _keys(
        action: AuthRateLimitAction, source: str, email: str
    ) -> tuple[str, str]:
        normalized_source = source.strip().casefold()
        if not normalized_source:
            raise ValueError("source must not be empty")
        normalized_email = normalize_email(email)
        source_digest = _digest_identifier(normalized_source)
        email_digest = _digest_identifier(normalized_email)
        prefix = f"auth:rate-limit:{action.value}"
        return (
            f"{prefix}:source:{source_digest}",
            f"{prefix}:email:{email_digest}",
        )


def _digest_identifier(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


auth_rate_limiter = AuthRateLimiter()


__all__ = [
    "AuthRateLimitAction",
    "AuthRateLimitDecision",
    "AuthRateLimitExceeded",
    "AuthRateLimitPolicy",
    "AuthRateLimiter",
    "AuthRateLimiterUnavailable",
    "auth_rate_limiter",
]
