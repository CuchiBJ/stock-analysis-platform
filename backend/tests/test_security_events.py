"""Security telemetry must remain operationally useful and secret-free."""

from __future__ import annotations

import asyncio
import json
import logging
from email.message import EmailMessage

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints.security_operations import security_status
from app.models.user import User, UserRole
from app.services.mailer import SMTPMailer
from app.services.security_events import (
    SecurityEventTracker,
    record_security_event,
    security_event_tracker,
)


def test_structured_event_contains_only_allowlisted_categorical_fields(caplog):
    security_event_tracker.reset_for_test()
    with caplog.at_level(logging.INFO, logger="security"):
        record_security_event(
            "auth_login", "failure", reason="invalid_credentials"
        )

    payload = json.loads(caplog.records[-1].message)
    assert payload == {
        "count": 1,
        "event": "security.auth_login",
        "outcome": "failure",
        "reason": "invalid_credentials",
    }
    rendered = caplog.records[-1].message
    for forbidden in ("@", "password", "token", "cookie", "session_id"):
        assert forbidden not in rendered.casefold()


def test_tracker_exposes_actionable_aggregate_checks_without_identity_data():
    tracker = SecurityEventTracker()
    tracker.increment("auth_login", "success", 5)
    tracker.increment("auth_login", "failure", 15)
    tracker.increment("mail_delivery", "failure")
    tracker.increment("session_created", "success", 4)
    tracker.increment("session_revoked", "success", 2)

    snapshot = tracker.snapshot()

    assert snapshot["login_failure_rate"] == 0.75
    assert snapshot["sessions_created"] == 4
    assert snapshot["sessions_revoked"] == 2
    assert snapshot["checks"] == {
        "auth_failure_rate": "warning",
        "mail_delivery": "warning",
        "rate_limit_backend": "ok",
    }
    assert not {"email", "user_id", "ip", "token"}.intersection(snapshot)


def test_security_operations_are_admin_only():
    security_event_tracker.reset_for_test()
    admin = User(
        email="admin@example.test",
        password_hash="not-returned",
        role=UserRole.ADMIN.value,
        state="active",
    )
    regular = User(
        email="user@example.test",
        password_hash="not-returned",
        role=UserRole.USER.value,
        state="active",
    )

    result = asyncio.run(security_status(admin))
    assert result["window"] == "since_process_start"
    assert "email" not in result

    with pytest.raises(HTTPException) as raised:
        asyncio.run(security_status(regular))
    assert raised.value.status_code == 403


def test_free_form_or_unknown_security_fields_are_rejected():
    with pytest.raises(ValueError, match="reason"):
        record_security_event(
            "auth_login",  # type: ignore[arg-type]
            "failure",
            reason="admin@example.test",
        )


def test_smtp_failure_increments_mail_check_without_logging_message_data(
    caplog, monkeypatch
):
    security_event_tracker.reset_for_test()
    mailer = object.__new__(SMTPMailer)
    message = EmailMessage()
    message["To"] = "private@example.test"
    message.set_content("https://app.example.test/reset-password?token=SECRET")

    def fail_delivery(_message):
        raise OSError("provider unavailable")

    monkeypatch.setattr(mailer, "_send_blocking", fail_delivery)
    with caplog.at_level(logging.INFO, logger="security"):
        with pytest.raises(OSError, match="provider unavailable"):
            asyncio.run(mailer._deliver(message, reason="password_reset"))

    assert security_event_tracker.snapshot()["mail_failures"] == 1
    rendered = caplog.records[-1].message
    assert "private@example.test" not in rendered
    assert "SECRET" not in rendered
