"""Transport contracts for public account and browser-session endpoints."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException, Response
from pydantic import ValidationError
from starlette.requests import Request

import app.api.v1.endpoints.auth as auth_api
from app.core.auth import AuthenticatedSession, SESSION_COOKIE_NAME
from app.models.user import AuthSession, User, UserProfile, UserRole, UserState
from app.schemas.auth import (
    EmailRequest,
    LoginRequest,
    PasswordResetRequest,
    RegistrationRequest,
    TokenRequest,
)
from app.services.auth_rate_limiter import AuthRateLimitAction, AuthRateLimitDecision
from app.services.auth_service import CreatedSession, IssuedAccountToken, digest_token
from app.services.mailer import CaptureMailer, EmailKind


UTC = timezone.utc
NOW = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)
SESSION_TOKEN = "S" * 43
CSRF_TOKEN = "C" * 43
ACTION_TOKEN = "A" * 43
VALID_PASSWORD = "a valid passphrase for 2026!"


class _Database:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


class _Limiter:
    def __init__(self):
        self.calls = []

    async def enforce(self, action, *, source, email):
        self.calls.append((action, source, email))
        return AuthRateLimitDecision(True, 0, 1, 1)


def _request(*, session_token=None) -> Request:
    headers = []
    if session_token is not None:
        headers.append(
            (b"cookie", f"{SESSION_COOKIE_NAME}={session_token}".encode("ascii"))
        )
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/test",
            "headers": headers,
            "client": ("203.0.113.10", 443),
        }
    )


def _user() -> User:
    user = User(
        id=uuid4(),
        email="person@example.com",
        password_hash="not-exposed",
        role=UserRole.USER.value,
        state=UserState.ACTIVE.value,
        email_verified_at=NOW,
    )
    user.profile = UserProfile(display_name="Person")
    return user


def _created_session(user: User) -> CreatedSession:
    return CreatedSession(
        session=AuthSession(
            user_id=user.id,
            token_digest=digest_token(SESSION_TOKEN),
            csrf_token_digest=digest_token(CSRF_TOKEN),
            expires_at=NOW + timedelta(days=30),
        ),
        session_token=SESSION_TOKEN,
        csrf_token=CSRF_TOKEN,
    )


@pytest.mark.parametrize("schema", [RegistrationRequest, EmailRequest])
def test_email_transport_schemas_reject_non_email_text(schema):
    values = {"email": "abc"}
    if schema is RegistrationRequest:
        values.update(password=VALID_PASSWORD, display_name="Person")

    with pytest.raises(ValidationError):
        schema(**values)


def test_registration_rejects_blank_display_name_and_normalizes_surrounding_space():
    with pytest.raises(ValidationError):
        RegistrationRequest(
            email="person@example.com",
            password=VALID_PASSWORD,
            display_name="   ",
        )

    payload = RegistrationRequest(
        email="person@example.com",
        password=VALID_PASSWORD,
        display_name="  Person Name  ",
    )
    assert payload.display_name == "Person Name"


@pytest.mark.parametrize("account_exists", [False, True])
def test_register_returns_same_accepted_message_for_new_and_duplicate_email(
    monkeypatch,
    account_exists,
):
    user = _user()
    issued = None if account_exists else IssuedAccountToken(user=user, token=ACTION_TOKEN)

    async def fake_register(*_args, **_kwargs):
        return issued

    monkeypatch.setattr(auth_api, "register_user", fake_register)
    db = _Database()
    limiter = _Limiter()
    mailer = CaptureMailer()

    result = asyncio.run(
        auth_api.register(
            RegistrationRequest(
                email="Person@Example.COM",
                password=VALID_PASSWORD,
                display_name="Person",
            ),
            _request(),
            None,
            db,
            limiter,
            mailer,
        )
    )

    assert result.message == auth_api.GENERIC_ACCOUNT_MESSAGE
    assert db.commits == 1
    assert db.rollbacks == 0
    assert limiter.calls == [
        (AuthRateLimitAction.REGISTRATION, "203.0.113.10", "Person@Example.COM")
    ]
    assert len(mailer.messages) == (0 if account_exists else 1)
    if mailer.messages:
        assert mailer.messages[0].kind == EmailKind.VERIFICATION
        assert mailer.messages[0].recipient == user.email
        assert f"token={ACTION_TOKEN}" in mailer.messages[0].action_url
        assert ACTION_TOKEN not in repr(mailer.messages[0])


@pytest.mark.parametrize("valid", [True, False])
def test_verify_email_commits_success_and_rolls_back_invalid_or_expired_token(
    monkeypatch,
    valid,
):
    async def fake_verify(*_args, **_kwargs):
        return _user() if valid else None

    monkeypatch.setattr(auth_api, "verify_email_token", fake_verify)
    db = _Database()

    if valid:
        result = asyncio.run(
            auth_api.verify_email(TokenRequest(token=ACTION_TOKEN), None, db)
        )
        assert result.message == "Email verified. You can now sign in."
        assert db.commits == 1
    else:
        with pytest.raises(HTTPException) as raised:
            asyncio.run(auth_api.verify_email(TokenRequest(token=ACTION_TOKEN), None, db))
        assert raised.value.status_code == 400
        assert raised.value.detail == auth_api.INVALID_TOKEN_ERROR
        assert db.rollbacks == 1


@pytest.mark.parametrize("eligible", [False, True])
def test_resend_verification_is_non_enumerating(monkeypatch, eligible):
    user = _user()
    issued = IssuedAccountToken(user=user, token=ACTION_TOKEN) if eligible else None

    async def fake_resend(*_args, **_kwargs):
        return issued

    monkeypatch.setattr(auth_api, "resend_verification_token", fake_resend)
    db = _Database()
    mailer = CaptureMailer()

    result = asyncio.run(
        auth_api.resend_verification(
            EmailRequest(email=user.email),
            _request(),
            None,
            db,
            _Limiter(),
            mailer,
        )
    )

    assert result.message == auth_api.GENERIC_ACCOUNT_MESSAGE
    assert db.commits == 1
    assert len(mailer.messages) == int(eligible)


def test_login_sets_secure_host_only_cookie_and_returns_separate_csrf_token(monkeypatch):
    user = _user()
    created = _created_session(user)

    async def fake_authenticate(*_args, **_kwargs):
        return user

    async def fake_create(*_args, **_kwargs):
        return created

    monkeypatch.setattr(auth_api, "authenticate_user", fake_authenticate)
    monkeypatch.setattr(auth_api, "create_session", fake_create)
    db = _Database()
    response = Response()

    result = asyncio.run(
        auth_api.login(
            LoginRequest(email=user.email, password=VALID_PASSWORD),
            _request(),
            response,
            None,
            db,
            _Limiter(),
        )
    )

    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"{SESSION_COOKIE_NAME}={SESSION_TOKEN};")
    assert "HttpOnly" in cookie
    assert "Secure" in cookie
    assert "SameSite=lax" in cookie
    assert "Path=/" in cookie
    assert "Domain=" not in cookie
    assert result.csrf_token == CSRF_TOKEN
    assert result.csrf_token != SESSION_TOKEN
    assert result.user.id == user.id
    assert db.commits == 1


def test_login_failure_is_generic_and_creates_no_cookie(monkeypatch):
    async def reject(*_args, **_kwargs):
        return None

    monkeypatch.setattr(auth_api, "authenticate_user", reject)
    db = _Database()
    response = Response()

    with pytest.raises(HTTPException) as raised:
        asyncio.run(
            auth_api.login(
                LoginRequest(email="missing@example.com", password="wrong"),
                _request(),
                response,
                None,
                db,
                _Limiter(),
            )
        )

    assert raised.value.status_code == 401
    assert raised.value.detail == auth_api.GENERIC_LOGIN_ERROR
    assert "set-cookie" not in response.headers
    assert db.rollbacks == 1


def test_current_session_rotates_csrf_proof(monkeypatch):
    user = _user()
    created = _created_session(user)
    principal = AuthenticatedSession(session=created.session, user=user)

    async def rotate(_db, _session):
        return "N" * 43

    monkeypatch.setattr(auth_api, "issue_session_csrf", rotate)
    db = _Database()

    result = asyncio.run(auth_api.current_session(principal, user, db))

    assert result.csrf_token == "N" * 43
    assert result.expires_at == created.expires_at
    assert db.commits == 1


def test_logout_revokes_server_session_and_expires_cookie(monkeypatch):
    revoked = []

    async def fake_revoke(_db, raw_token):
        revoked.append(raw_token)
        return True

    monkeypatch.setattr(auth_api, "revoke_current_session", fake_revoke)
    db = _Database()
    response = Response()

    result = asyncio.run(
        auth_api.logout(
            _request(session_token=SESSION_TOKEN),
            response,
            _user(),
            db,
        )
    )

    assert result.message == "Signed out."
    assert revoked == [SESSION_TOKEN]
    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f'{SESSION_COOKIE_NAME}="";')
    assert "Max-Age=0" in cookie
    assert "HttpOnly" in cookie and "Secure" in cookie
    assert db.commits == 1


@pytest.mark.parametrize("eligible", [False, True])
def test_forgot_password_is_non_enumerating(monkeypatch, eligible):
    user = _user()
    issued = IssuedAccountToken(user=user, token=ACTION_TOKEN) if eligible else None

    async def fake_issue(*_args, **_kwargs):
        return issued

    monkeypatch.setattr(auth_api, "issue_password_reset_token", fake_issue)
    db = _Database()
    mailer = CaptureMailer()

    result = asyncio.run(
        auth_api.forgot_password(
            EmailRequest(email=user.email),
            _request(),
            None,
            db,
            _Limiter(),
            mailer,
        )
    )

    assert result.message == auth_api.GENERIC_ACCOUNT_MESSAGE
    assert db.commits == 1
    assert len(mailer.messages) == int(eligible)
    if eligible:
        assert mailer.messages[0].kind == EmailKind.PASSWORD_RESET


@pytest.mark.parametrize("valid", [True, False])
def test_complete_password_reset_commits_only_valid_single_use_token(monkeypatch, valid):
    async def fake_reset(*_args, **_kwargs):
        return _user() if valid else None

    monkeypatch.setattr(auth_api, "reset_password", fake_reset)
    db = _Database()
    payload = PasswordResetRequest(
        token=ACTION_TOKEN,
        new_password="a completely new password 2026!",
    )

    if valid:
        result = asyncio.run(auth_api.complete_password_reset(payload, None, db))
        assert result.message.startswith("Password updated")
        assert db.commits == 1
    else:
        with pytest.raises(HTTPException) as raised:
            asyncio.run(auth_api.complete_password_reset(payload, None, db))
        assert raised.value.status_code == 400
        assert raised.value.detail == auth_api.INVALID_TOKEN_ERROR
        assert db.rollbacks == 1
