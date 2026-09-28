"""Unit contracts for the identity and authentication primitives.

These tests intentionally exercise only pure/model behavior.  Database and API
integration belongs to the later authentication tasks in the OpenSpec change.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.models.user import (
    EmailVerificationToken,
    PasswordResetToken,
    User,
    UserRole,
    UserState,
    normalize_email,
)


UTC = timezone.utc


def test_email_normalization_trims_and_casefolds_the_address():
    assert normalize_email("  Trader.Example@EXAMPLE.COM  ") == "trader.example@example.com"


def test_equivalent_email_spellings_normalize_to_one_identity():
    variants = {
        normalize_email("owner@example.com"),
        normalize_email(" OWNER@example.com "),
        normalize_email("Owner@Example.Com"),
    }

    assert variants == {"owner@example.com"}


def test_user_constructor_persists_only_the_normalized_email():
    user = User(email="  Owner@Example.COM ", password_hash="not-a-real-hash")

    assert user.email == "owner@example.com"


def test_new_user_is_non_privileged_and_pending_verification():
    user = User(email="new@example.com", password_hash="not-a-real-hash")

    assert user.role == UserRole.USER
    assert user.state == UserState.PENDING_VERIFICATION
    assert user.email_verified_at is None


def test_pending_user_can_activate_only_by_recording_email_verification():
    verified_at = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)
    user = User(
        email="new@example.com",
        password_hash="not-a-real-hash",
        role=UserRole.USER.value,
        state=UserState.PENDING_VERIFICATION.value,
    )

    user.activate(verified_at)

    assert user.state == UserState.ACTIVE
    assert user.email_verified_at == verified_at


@pytest.mark.parametrize("initial_state", [UserState.PENDING_VERIFICATION, UserState.ACTIVE])
def test_account_can_be_disabled_from_a_non_disabled_state(initial_state):
    user = User(
        email="user@example.com",
        password_hash="not-a-real-hash",
        state=initial_state.value,
    )

    user.disable()

    assert user.state == UserState.DISABLED


def test_disabled_account_cannot_be_reactivated_by_normal_verification_flow():
    user = User(
        email="disabled@example.com",
        password_hash="not-a-real-hash",
        state=UserState.DISABLED.value,
    )

    with pytest.raises(ValueError):
        user.activate(datetime(2026, 9, 22, 12, 0, tzinfo=UTC))


@pytest.mark.parametrize("token_type", [EmailVerificationToken, PasswordResetToken])
def test_action_token_is_usable_before_expiry(token_type):
    now = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)
    token = token_type(
        user_id=uuid4(),
        token_digest="a" * 64,
        expires_at=now + timedelta(minutes=1),
    )

    assert token.is_expired(now) is False
    assert token.is_usable(now) is True


@pytest.mark.parametrize("token_type", [EmailVerificationToken, PasswordResetToken])
def test_action_token_is_expired_at_the_exact_expiry_boundary(token_type):
    expires_at = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)
    token = token_type(
        user_id=uuid4(),
        token_digest="a" * 64,
        expires_at=expires_at,
    )

    assert token.is_expired(expires_at) is True
    assert token.is_usable(expires_at) is False


@pytest.mark.parametrize("token_type", [EmailVerificationToken, PasswordResetToken])
def test_action_token_can_be_consumed_only_once(token_type):
    now = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)
    token = token_type(
        user_id=uuid4(),
        token_digest="a" * 64,
        expires_at=now + timedelta(hours=1),
    )

    assert token.consume(now) is True
    assert token.consumed_at == now
    assert token.is_usable(now) is False
    assert token.consume(now + timedelta(seconds=1)) is False
    assert token.consumed_at == now


@pytest.mark.parametrize("token_type", [EmailVerificationToken, PasswordResetToken])
def test_expired_action_token_cannot_be_consumed(token_type):
    now = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)
    token = token_type(
        user_id=uuid4(),
        token_digest="a" * 64,
        expires_at=now - timedelta(microseconds=1),
    )

    assert token.consume(now) is False
    assert token.consumed_at is None


@pytest.mark.parametrize("token_type", [EmailVerificationToken, PasswordResetToken])
def test_action_token_models_have_no_raw_token_field(token_type):
    assert "token_digest" in token_type.__table__.columns
    assert "token" not in token_type.__table__.columns
