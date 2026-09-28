"""Adversarial contracts for session, account-state, CSRF, and Origin checks."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException
from starlette.requests import Request

import app.core.auth as auth_dependencies
from app.core.auth import (
    AuthenticatedSession,
    SESSION_COOKIE_NAME,
    get_current_active_user,
    get_current_session,
    parse_session_cookie,
    require_csrf_token,
    require_trusted_origin,
)
from app.models.user import AuthSession, User, UserState
from app.services.auth_service import (
    SESSION_ABSOLUTE_LIFETIME,
    create_session,
    digest_token,
    generate_token,
    lookup_session,
    revoke_all_sessions,
    revoke_current_session,
)


UTC = timezone.utc
NOW = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)


def _request_with_session(token: str | None) -> Request:
    headers = []
    if token is not None:
        headers.append((b"cookie", f"{SESSION_COOKIE_NAME}={token}".encode("ascii")))
    return Request({"type": "http", "method": "GET", "path": "/", "headers": headers})


def _user(*, state: UserState = UserState.ACTIVE, verified: bool = True) -> User:
    return User(
        id=uuid4(),
        email="security-test@example.com",
        password_hash="not-a-real-hash",
        state=state.value,
        email_verified_at=NOW if verified else None,
    )


def _principal(*, csrf_token: str | None = None) -> AuthenticatedSession:
    user = _user()
    session = AuthSession(
        user_id=user.id,
        token_digest=digest_token(generate_token()),
        csrf_token_digest=digest_token(csrf_token or generate_token()),
        expires_at=NOW + timedelta(days=1),
    )
    return AuthenticatedSession(session=session, user=user)


@pytest.mark.parametrize("raw_cookie", [None, "", "short", "contains+padding="])
def test_missing_or_malformed_session_cookie_is_rejected_without_fallback(raw_cookie):
    with pytest.raises(HTTPException) as raised:
        parse_session_cookie(_request_with_session(raw_cookie))

    assert raised.value.status_code == 401
    assert raised.value.headers == {"WWW-Authenticate": "Session"}


@pytest.mark.parametrize("session_failure", ["invalid", "expired", "revoked"])
def test_invalid_expired_and_revoked_session_results_are_all_unauthenticated(
    monkeypatch,
    session_failure,
):
    async def no_active_session(_db, _raw_token):
        return None

    monkeypatch.setattr(auth_dependencies, "lookup_session", no_active_session)
    request = _request_with_session("A" * 43)

    with pytest.raises(HTTPException) as raised:
        asyncio.run(get_current_session(request, object()))

    assert raised.value.status_code == 401, session_failure
    assert raised.value.detail == "Not authenticated"


def test_session_lookup_query_excludes_revoked_and_expired_rows():
    class _Result:
        def scalar_one_or_none(self):
            return None

    class _Database:
        statement = None

        async def execute(self, statement):
            self.statement = statement
            return _Result()

    db = _Database()

    assert asyncio.run(lookup_session(db, "A" * 43, now=NOW)) is None
    sql = str(db.statement).lower()
    assert "auth_sessions.revoked_at is null" in sql
    assert "auth_sessions.expires_at >" in sql


def test_session_creation_uses_independent_digested_secrets_and_30_day_expiry():
    class _Database:
        def __init__(self):
            self.added = []
            self.flush_count = 0

        def add(self, value):
            self.added.append(value)

        async def flush(self):
            self.flush_count += 1

    db = _Database()
    user_id = uuid4()

    created = asyncio.run(create_session(db, user_id, now=NOW))

    assert db.added == [created.session]
    assert db.flush_count == 1
    assert created.session.user_id == user_id
    assert created.expires_at == NOW + SESSION_ABSOLUTE_LIFETIME
    assert SESSION_ABSOLUTE_LIFETIME == timedelta(days=30)
    assert created.session_token != created.csrf_token
    assert created.session.token_digest == digest_token(created.session_token)
    assert created.session.csrf_token_digest == digest_token(created.csrf_token)
    assert created.session_token not in vars(created.session).values()
    assert created.csrf_token not in vars(created.session).values()


def test_current_session_revocation_targets_only_active_matching_digest():
    class _Result:
        rowcount = 1

    class _Database:
        statement = None
        flush_count = 0

        async def execute(self, statement):
            self.statement = statement
            return _Result()

        async def flush(self):
            self.flush_count += 1

    db = _Database()
    raw_token = "A" * 43

    changed = asyncio.run(revoke_current_session(db, raw_token, now=NOW))

    assert changed is True
    assert db.flush_count == 1
    sql = str(db.statement).lower()
    assert sql.startswith("update auth_sessions")
    assert "auth_sessions.token_digest" in sql
    assert "auth_sessions.revoked_at is null" in sql
    params = db.statement.compile().params.values()
    assert digest_token(raw_token) in params
    assert raw_token not in params


def test_all_session_revocation_is_scoped_to_one_user_and_reports_count():
    class _Result:
        rowcount = 3

    class _Database:
        statement = None
        flush_count = 0

        async def execute(self, statement):
            self.statement = statement
            return _Result()

        async def flush(self):
            self.flush_count += 1

    db = _Database()
    user_id = uuid4()

    count = asyncio.run(revoke_all_sessions(db, user_id, now=NOW))

    assert count == 3
    assert db.flush_count == 1
    sql = str(db.statement).lower()
    assert "auth_sessions.user_id" in sql
    assert "auth_sessions.revoked_at is null" in sql
    assert user_id in db.statement.compile().params.values()


@pytest.mark.parametrize(
    ("state", "verified"),
    [
        (UserState.DISABLED, True),
        (UserState.PENDING_VERIFICATION, False),
        (UserState.ACTIVE, False),
    ],
)
def test_non_active_or_unverified_user_is_forbidden(state, verified):
    with pytest.raises(HTTPException) as raised:
        asyncio.run(get_current_active_user(_user(state=state, verified=verified)))

    assert raised.value.status_code == 403
    assert raised.value.detail == "Account is not active"


@pytest.mark.parametrize("csrf_token", [None, "too-short", "B" * 43])
def test_missing_malformed_or_incorrect_csrf_proof_is_forbidden(csrf_token):
    principal = _principal(csrf_token="A" * 43)

    with pytest.raises(HTTPException) as raised:
        asyncio.run(require_csrf_token(principal, csrf_token))

    assert raised.value.status_code == 403
    assert raised.value.detail == "CSRF validation failed"


@pytest.mark.parametrize(
    "origin",
    [
        None,
        "null",
        "https://evil.example",
        "https://app.example.evil.example",
        "https://app.example/extra-path",
    ],
)
def test_missing_or_hostile_origin_is_forbidden(monkeypatch, origin):
    monkeypatch.setattr(
        auth_dependencies,
        "configured_trusted_origins",
        lambda: frozenset({"https://app.example"}),
    )

    with pytest.raises(HTTPException) as raised:
        asyncio.run(require_trusted_origin(origin))

    assert raised.value.status_code == 403
    assert raised.value.detail == "Origin not allowed"
