"""Token-free structured security events and process-local operational signals.

Events deliberately accept only a small allow-list of categorical fields. They
must never contain email addresses, user IDs, IP addresses, cookies, passwords,
raw tokens, URLs with tokens, or session digests.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from threading import Lock
from typing import Literal, Optional


logger = logging.getLogger("security")

SecurityEventName = Literal[
    "auth_login",
    "auth_rate_limit",
    "mail_delivery",
    "session_created",
    "session_revoked",
]
SecurityOutcome = Literal["success", "failure", "blocked", "unavailable"]

_ALLOWED_EVENTS = {
    "auth_login",
    "auth_rate_limit",
    "mail_delivery",
    "session_created",
    "session_revoked",
}
_ALLOWED_OUTCOMES = {"success", "failure", "blocked", "unavailable"}
_SAFE_REASONS = {
    "invalid_credentials",
    "limit_exceeded",
    "backend_unavailable",
    "smtp_error",
    "verification",
    "password_reset",
    "logout",
    "password_changed",
    "admin_reset",
}


class SecurityEventTracker:
    """Maintain coarse counters suitable for one-worker operational checks."""

    def __init__(self) -> None:
        self._counts: Counter[str] = Counter()
        self._lock = Lock()

    def increment(self, event: str, outcome: str, count: int = 1) -> None:
        if count < 0:
            raise ValueError("security event count must not be negative")
        with self._lock:
            self._counts[f"{event}:{outcome}"] += count

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            counts = dict(self._counts)
        login_successes = counts.get("auth_login:success", 0)
        login_failures = counts.get("auth_login:failure", 0)
        login_attempts = login_successes + login_failures
        failure_rate = (
            round(login_failures / login_attempts, 4) if login_attempts else 0.0
        )
        mail_failures = counts.get("mail_delivery:failure", 0)
        rate_limit_unavailable = counts.get("auth_rate_limit:unavailable", 0)
        return {
            "window": "since_process_start",
            "login_attempts": login_attempts,
            "login_failures": login_failures,
            "login_failure_rate": failure_rate,
            "mail_failures": mail_failures,
            "sessions_created": counts.get("session_created:success", 0),
            "sessions_revoked": counts.get("session_revoked:success", 0),
            "rate_limit_blocks": counts.get("auth_rate_limit:blocked", 0),
            "rate_limit_backend_failures": rate_limit_unavailable,
            "checks": {
                "auth_failure_rate": (
                    "warning"
                    if login_attempts >= 20 and failure_rate >= 0.5
                    else "ok"
                ),
                "mail_delivery": "warning" if mail_failures else "ok",
                "rate_limit_backend": (
                    "warning" if rate_limit_unavailable else "ok"
                ),
            },
        }

    def reset_for_test(self) -> None:
        with self._lock:
            self._counts.clear()


security_event_tracker = SecurityEventTracker()


def record_security_event(
    event: SecurityEventName,
    outcome: SecurityOutcome,
    *,
    reason: Optional[str] = None,
    count: int = 1,
) -> None:
    """Emit one JSON event containing categorical, non-identifying fields only."""

    if event not in _ALLOWED_EVENTS:
        raise ValueError("unsupported security event")
    if outcome not in _ALLOWED_OUTCOMES:
        raise ValueError("unsupported security event outcome")
    if reason is not None and reason not in _SAFE_REASONS:
        raise ValueError("unsupported security event reason")

    security_event_tracker.increment(event, outcome, count)
    payload: dict[str, object] = {
        "event": f"security.{event}",
        "outcome": outcome,
        "count": count,
    }
    if reason is not None:
        payload["reason"] = reason
    logger.info(json.dumps(payload, sort_keys=True, separators=(",", ":")))


__all__ = [
    "SecurityEventTracker",
    "record_security_event",
    "security_event_tracker",
]
