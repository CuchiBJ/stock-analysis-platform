"""Account-flow contracts below the HTTP transport boundary."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

import app.services.auth_service as auth_service
from app.models.user import (
    EmailVerificationToken,
    PasswordResetToken,
    User,
    UserRole,
    UserState,
)
from app.schemas.auth import RegistrationRequest
from app.services.auth_service import (
    EMAIL_VERIFICATION_LIFETIME,
    PASSWORD_RESET_LIFETIME,
    authenticate_user,
    digest_token,
    issue_password_reset_token,
    register_user,
    resend_verification_token,
    reset_password,
    verify_email_token,
    verify_password,
)


UTC = timezone.utc
NOW = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)
VALID_PASSWORD = "a valid passphrase for 2026!"


class _MutationResult:
    rowcount = 0


class _FakeDatabase:
    def __init__(self, *scalar_results):
        self.scalar_results = iter(scalar_results)
        self.added = []
        self.statements = []
        self.flush_count = 0

    async def scalar(self, statement):
        self.statements.append(statement)
        return next(self.scalar_results)

    async def execute(self, statement):
        self.statements.append(statement)
        return _MutationResult()

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        self.flush_count += 1
        for value in self.added:
            if hasattr(value, "id") and value.id is None:
                value.id = uuid4()


def _user(*, state=UserState.ACTIVE, verified=True, password=VALID_PASSWORD):
    return User(
        id=uuid4(),
        email="person@example.com",
        password_hash=auth_service.hash_password(password),
        state=state.value,
        email_verified_at=NOW if verified else None,
    )


def test_registration_creates_pending_user_profile_and_24_hour_digest_only_token():
    db = _FakeDatabase(None)

    issued = asyncio.run(
        register_user(
            db,
            email="  New.User@Example.COM ",
            password=VALID_PASSWORD,
            display_name="  New User  ",
            now=NOW,
        )
    )

    assert issued is not None
    assert issued.user.email == "new.user@example.com"
    assert issued.user.role == UserRole.USER
    assert issued.user.state == UserState.PENDING_VERIFICATION
    assert issued.user.profile.display_name == "New User"
    assert verify_password(VALID_PASSWORD, issued.user.password_hash) is True
    token = next(value for value in db.added if isinstance(value, EmailVerificationToken))
    assert token.token_digest == digest_token(issued.token)
    assert token.expires_at == NOW + EMAIL_VERIFICATION_LIFETIME
    assert EMAIL_VERIFICATION_LIFETIME == timedelta(hours=24)
    assert "token" not in token.__table__.columns


def test_duplicate_registration_returns_same_non_exceptional_service_shape_and_adds_nothing():
    db = _FakeDatabase(uuid4())

    issued = asyncio.run(
        register_user(
            db,
            email="EXISTING@example.com",
            password=VALID_PASSWORD,
            display_name="Existing",
            now=NOW,
        )
    )

    assert issued is None
    assert db.added == []


def test_registration_transport_rejects_role_injection():
    with pytest.raises(ValidationError):
        RegistrationRequest(
            email="new@example.com",
            password=VALID_PASSWORD,
            display_name="New User",
            role="admin",
        )


def test_registration_rejects_password_outside_server_policy_before_persistence():
    db = _FakeDatabase(None)

    with pytest.raises(ValueError):
        asyncio.run(
            register_user(
                db,
                email="new@example.com",
                password="too-short",
                display_name="New User",
                now=NOW,
            )
        )

    assert db.added == []


def test_verification_activates_and_consumes_token_once():
    user = _user(state=UserState.PENDING_VERIFICATION, verified=False)
    token = EmailVerificationToken(
        user_id=user.id,
        token_digest=digest_token("A" * 43),
        expires_at=NOW + timedelta(minutes=1),
    )
    token.user = user
    db = _FakeDatabase(token, None)

    activated = asyncio.run(verify_email_token(db, "A" * 43, now=NOW))
    reused = asyncio.run(verify_email_token(db, "A" * 43, now=NOW + timedelta(seconds=1)))

    assert activated is user
    assert user.state == UserState.ACTIVE
    assert user.email_verified_at == NOW
    assert token.consumed_at == NOW
    assert reused is None


def test_expired_verification_token_is_rejected_by_the_persistence_query():
    db = _FakeDatabase(None)

    assert asyncio.run(verify_email_token(db, "A" * 43, now=NOW)) is None
    sql = str(db.statements[0]).lower()
    assert "email_verification_tokens.consumed_at is null" in sql
    assert "email_verification_tokens.expires_at >" in sql


def test_resend_is_generic_for_ineligible_email_and_replaces_old_token_for_pending_user():
    pending = _user(state=UserState.PENDING_VERIFICATION, verified=False)
    missing_db = _FakeDatabase(None)
    pending_db = _FakeDatabase(pending)

    missing = asyncio.run(
        resend_verification_token(missing_db, "missing@example.com", now=NOW)
    )
    replacement = asyncio.run(
        resend_verification_token(pending_db, pending.email, now=NOW)
    )

    assert missing is None
    assert missing_db.added == []
    assert replacement is not None
    assert replacement.user is pending
    assert any(isinstance(value, EmailVerificationToken) for value in pending_db.added)


@pytest.mark.parametrize(
    ("state", "verified", "password", "accepted"),
    [
        (UserState.ACTIVE, True, VALID_PASSWORD, True),
        (UserState.ACTIVE, True, "wrong password", False),
        (UserState.PENDING_VERIFICATION, False, VALID_PASSWORD, False),
        (UserState.DISABLED, True, VALID_PASSWORD, False),
    ],
)
def test_login_accepts_only_valid_credentials_for_active_verified_user(
    state,
    verified,
    password,
    accepted,
):
    user = _user(state=state, verified=verified)
    db = _FakeDatabase(user)

    result = asyncio.run(
        authenticate_user(db, email=" PERSON@EXAMPLE.COM ", password=password)
    )

    assert (result is user) is accepted


def test_unknown_login_still_invokes_constant_shape_password_check(monkeypatch):
    calls = []

    def record(password, encoded_hash):
        calls.append((password, encoded_hash))
        return False

    monkeypatch.setattr(auth_service, "verify_password_or_dummy", record)

    result = asyncio.run(
        authenticate_user(
            _FakeDatabase(None),
            email="missing@example.com",
            password="submitted password",
        )
    )

    assert result is None
    assert calls == [("submitted password", None)]


def test_password_recovery_is_generic_for_unknown_email_and_issues_60_minute_token_for_active_user(
):
    user = _user()
    missing_db = _FakeDatabase(None)
    active_db = _FakeDatabase(user)

    missing = asyncio.run(
        issue_password_reset_token(missing_db, "missing@example.com", now=NOW)
    )
    issued = asyncio.run(issue_password_reset_token(active_db, user.email, now=NOW))

    assert missing is None
    assert missing_db.added == []
    assert issued is not None
    token = next(value for value in active_db.added if isinstance(value, PasswordResetToken))
    assert token.token_digest == digest_token(issued.token)
    assert token.expires_at == NOW + PASSWORD_RESET_LIFETIME
    assert PASSWORD_RESET_LIFETIME == timedelta(minutes=60)


def test_password_reset_is_single_use_and_revokes_all_sessions(monkeypatch):
    user = _user()
    original_hash = user.password_hash
    token = PasswordResetToken(
        user_id=user.id,
        token_digest=digest_token("R" * 43),
        expires_at=NOW + timedelta(minutes=1),
    )
    token.user = user
    db = _FakeDatabase(token, None)
    revocations = []

    async def record_revocation(_db, user_id, *, now=None):
        revocations.append((user_id, now))
        return 2

    monkeypatch.setattr(auth_service, "revoke_all_sessions", record_revocation)

    changed = asyncio.run(
        reset_password(
            db,
            raw_token="R" * 43,
            new_password="a completely new password 2026!",
            now=NOW,
        )
    )
    reused = asyncio.run(
        reset_password(
            db,
            raw_token="R" * 43,
            new_password="another valid password 2026!",
            now=NOW + timedelta(seconds=1),
        )
    )

    assert changed is user
    assert reused is None
    assert user.password_hash != original_hash
    assert verify_password("a completely new password 2026!", user.password_hash) is True
    assert token.consumed_at == NOW
    assert revocations == [(user.id, NOW)]


def test_expired_password_reset_token_is_rejected_by_the_persistence_query():
    db = _FakeDatabase(None)

    result = asyncio.run(
        reset_password(
            db,
            raw_token="R" * 43,
            new_password="a completely new password 2026!",
            now=NOW,
        )
    )

    assert result is None
    sql = str(db.statements[0]).lower()
    assert "password_reset_tokens.consumed_at is null" in sql
    assert "password_reset_tokens.expires_at >" in sql
