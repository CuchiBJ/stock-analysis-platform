"""Pure authentication primitives shared by the account and session services.

Raw opaque tokens are returned only to the caller that must deliver them to the
browser or email recipient.  Persistence code stores :func:`digest_token`
outputs exclusively.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from pwdlib import PasswordHash
from pwdlib.exceptions import PwdlibError
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import (
    AuthSession,
    EmailVerificationToken,
    PasswordResetToken,
    User,
    UserProfile,
    UserRole,
    UserState,
    normalize_email,
)
from app.services.security_events import record_security_event


PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 1024
# Backward-compatible short names for internal callers and tests.
MIN_PASSWORD_LENGTH = PASSWORD_MIN_LENGTH
MAX_PASSWORD_LENGTH = PASSWORD_MAX_LENGTH
TOKEN_BYTES = 32
SESSION_ABSOLUTE_LIFETIME = timedelta(days=30)
EMAIL_VERIFICATION_LIFETIME = timedelta(hours=24)
PASSWORD_RESET_LIFETIME = timedelta(minutes=60)

_password_hash = PasswordHash.recommended()
# Used when an account lookup fails so password verification still performs one
# Argon2id operation.  The value is process-local and never represents a user.
_dummy_password_hash = _password_hash.hash("constant-shape-authentication-placeholder")


class PasswordPolicyError(ValueError):
    """Raised when a password violates the bounded server policy."""


def validate_password(password: str) -> str:
    """Validate the bounded password policy and return the unchanged secret."""
    if not isinstance(password, str):
        raise PasswordPolicyError("password must be a string")
    if len(password) < PASSWORD_MIN_LENGTH:
        raise PasswordPolicyError(
            f"password must contain at least {PASSWORD_MIN_LENGTH} characters"
        )
    if len(password) > PASSWORD_MAX_LENGTH:
        raise PasswordPolicyError(
            f"password must contain at most {PASSWORD_MAX_LENGTH} characters"
        )
    return password


def hash_password(password: str) -> str:
    """Hash a policy-compliant password with the recommended Argon2id settings."""
    return _password_hash.hash(validate_password(password))


def verify_password(password: str, encoded_hash: str) -> bool:
    """Return False for malformed hashes instead of leaking backend errors."""
    try:
        return _password_hash.verify(password, encoded_hash)
    except (PwdlibError, TypeError, ValueError):
        return False


def verify_password_or_dummy(password: str, encoded_hash: str | None) -> bool:
    """Perform an Argon2id check even when no account hash was found."""
    candidate_hash = encoded_hash or _dummy_password_hash
    verified = verify_password(password, candidate_hash)
    return bool(encoded_hash) and verified


# Descriptive alias kept for callers that prefer to name the timing property.
verify_password_constant_shape = verify_password_or_dummy


def generate_token() -> str:
    """Generate an opaque URL-safe token with at least 256 bits of entropy."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def digest_token(raw_token: str) -> str:
    """Return the lowercase SHA-256 hex digest persisted for an opaque token."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def token_matches(raw_token: str, stored_digest: str) -> bool:
    """Compare an opaque token with its stored digest in constant time."""
    candidate_digest = digest_token(raw_token)
    return hmac.compare_digest(candidate_digest, stored_digest)


@dataclass(frozen=True)
class CreatedSession:
    """A newly persisted session and the secrets delivered once to its client."""

    session: AuthSession
    session_token: str
    csrf_token: str

    @property
    def expires_at(self) -> datetime:
        return self.session.expires_at


@dataclass(frozen=True)
class IssuedAccountToken:
    """A user plus an action token that must be delivered exactly once."""

    user: User
    token: str


def utcnow() -> datetime:
    """Return an aware UTC timestamp; injectable ``now`` values keep tests deterministic."""

    return datetime.now(timezone.utc)


async def create_session(
    db: AsyncSession,
    user_id: UUID,
    *,
    now: Optional[datetime] = None,
) -> CreatedSession:
    """Create a 30-day opaque session and its independent CSRF secret.

    The caller is responsible for committing its transaction.  Only digests are
    attached to the ORM model; the raw values exist solely in the return value.
    """

    issued_at = now or utcnow()
    session_token = generate_token()
    csrf_token = generate_token()
    session = AuthSession(
        user_id=user_id,
        token_digest=digest_token(session_token),
        csrf_token_digest=digest_token(csrf_token),
        expires_at=issued_at + SESSION_ABSOLUTE_LIFETIME,
    )
    db.add(session)
    await db.flush()
    record_security_event("session_created", "success")
    return CreatedSession(
        session=session,
        session_token=session_token,
        csrf_token=csrf_token,
    )


async def issue_session_csrf(db: AsyncSession, session: AuthSession) -> str:
    """Rotate and return the CSRF proof for an existing active session."""

    csrf_token = generate_token()
    session.csrf_token_digest = digest_token(csrf_token)
    await db.flush()
    return csrf_token


async def lookup_session(
    db: AsyncSession,
    raw_token: str,
    *,
    now: Optional[datetime] = None,
) -> Optional[AuthSession]:
    """Resolve an active, unexpired session by the digest of its opaque token."""

    if not raw_token:
        return None
    checked_at = now or utcnow()
    result = await db.execute(
        select(AuthSession)
        .options(selectinload(AuthSession.user).selectinload(User.profile))
        .where(
            AuthSession.token_digest == digest_token(raw_token),
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > checked_at,
        )
    )
    return result.scalar_one_or_none()


async def revoke_current_session(
    db: AsyncSession,
    raw_token: str,
    *,
    now: Optional[datetime] = None,
) -> bool:
    """Revoke the session identified by ``raw_token`` and report if it changed."""

    if not raw_token:
        return False
    revoked_at = now or utcnow()
    result = await db.execute(
        update(AuthSession)
        .where(
            AuthSession.token_digest == digest_token(raw_token),
            AuthSession.revoked_at.is_(None),
        )
        .values(revoked_at=revoked_at)
    )
    await db.flush()
    revoked = bool(result.rowcount)
    if revoked:
        record_security_event(
            "session_revoked", "success", reason="logout"
        )
    return revoked


async def revoke_all_sessions(
    db: AsyncSession,
    user_id: UUID,
    *,
    now: Optional[datetime] = None,
) -> int:
    """Revoke every currently non-revoked session belonging to one user."""

    revoked_at = now or utcnow()
    result = await db.execute(
        update(AuthSession)
        .where(
            AuthSession.user_id == user_id,
            AuthSession.revoked_at.is_(None),
        )
        .values(revoked_at=revoked_at)
    )
    await db.flush()
    revoked_count = int(result.rowcount or 0)
    if revoked_count:
        record_security_event(
            "session_revoked",
            "success",
            reason="password_changed",
            count=revoked_count,
        )
    return revoked_count


# A concise alias for callers that do not need to distinguish logout semantics.
revoke_session = revoke_current_session


async def register_user(
    db: AsyncSession,
    *,
    email: str,
    password: str,
    display_name: str,
    now: Optional[datetime] = None,
) -> Optional[IssuedAccountToken]:
    """Create a pending non-privileged account/profile and verification token.

    ``None`` deliberately represents an existing normalized email so the HTTP
    layer can return the same accepted response without exposing account state.
    The caller owns the surrounding transaction.
    """

    canonical_email = normalize_email(email)
    existing = await db.scalar(select(User.id).where(User.email == canonical_email))
    if existing is not None:
        return None

    user = User(
        email=canonical_email,
        password_hash=hash_password(password),
        role=UserRole.USER.value,
        state=UserState.PENDING_VERIFICATION.value,
    )
    user.profile = UserProfile(display_name=display_name)
    db.add(user)
    await db.flush()
    return await issue_verification_token(db, user, now=now)


async def issue_verification_token(
    db: AsyncSession,
    user: User,
    *,
    now: Optional[datetime] = None,
) -> IssuedAccountToken:
    """Invalidate older verification tokens and issue a new 24-hour token."""

    issued_at = now or utcnow()
    await db.execute(
        update(EmailVerificationToken)
        .where(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.consumed_at.is_(None),
        )
        .values(consumed_at=issued_at)
    )
    raw_token = generate_token()
    db.add(
        EmailVerificationToken(
            user_id=user.id,
            token_digest=digest_token(raw_token),
            expires_at=issued_at + EMAIL_VERIFICATION_LIFETIME,
        )
    )
    await db.flush()
    return IssuedAccountToken(user=user, token=raw_token)


async def resend_verification_token(
    db: AsyncSession,
    email: str,
    *,
    now: Optional[datetime] = None,
) -> Optional[IssuedAccountToken]:
    """Issue a replacement only for an eligible account, without enumeration."""

    canonical_email = normalize_email(email)
    user = await db.scalar(
        select(User).where(
            User.email == canonical_email,
            User.state == UserState.PENDING_VERIFICATION.value,
            User.email_verified_at.is_(None),
        )
    )
    if user is None:
        return None
    return await issue_verification_token(db, user, now=now)


async def verify_email_token(
    db: AsyncSession,
    raw_token: str,
    *,
    now: Optional[datetime] = None,
) -> Optional[User]:
    """Consume a valid verification token and activate its pending account."""

    checked_at = now or utcnow()
    token = await db.scalar(
        select(EmailVerificationToken)
        .options(selectinload(EmailVerificationToken.user))
        .where(
            EmailVerificationToken.token_digest == digest_token(raw_token),
            EmailVerificationToken.consumed_at.is_(None),
            EmailVerificationToken.expires_at > checked_at,
        )
        .with_for_update()
    )
    if token is None or token.user.state != UserState.PENDING_VERIFICATION.value:
        return None

    token.consumed_at = checked_at
    token.user.activate(checked_at)
    await db.execute(
        update(EmailVerificationToken)
        .where(
            EmailVerificationToken.user_id == token.user_id,
            EmailVerificationToken.consumed_at.is_(None),
        )
        .values(consumed_at=checked_at)
    )
    await db.flush()
    return token.user


async def authenticate_user(
    db: AsyncSession,
    *,
    email: str,
    password: str,
) -> Optional[User]:
    """Authenticate only a verified active user with constant-shape failures."""

    canonical_email = normalize_email(email)
    user = await db.scalar(
        select(User)
        .options(selectinload(User.profile))
        .where(User.email == canonical_email)
    )
    password_valid = verify_password_or_dummy(
        password,
        user.password_hash if user is not None else None,
    )
    if (
        user is None
        or not password_valid
        or user.state != UserState.ACTIVE.value
        or user.email_verified_at is None
    ):
        return None
    return user


async def issue_password_reset_token(
    db: AsyncSession,
    email: str,
    *,
    now: Optional[datetime] = None,
) -> Optional[IssuedAccountToken]:
    """Issue a 60-minute reset token only for an active verified account."""

    canonical_email = normalize_email(email)
    user = await db.scalar(
        select(User).where(
            User.email == canonical_email,
            User.state == UserState.ACTIVE.value,
            User.email_verified_at.is_not(None),
        )
    )
    if user is None:
        return None

    issued_at = now or utcnow()
    await db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.consumed_at.is_(None),
        )
        .values(consumed_at=issued_at)
    )
    raw_token = generate_token()
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_digest=digest_token(raw_token),
            expires_at=issued_at + PASSWORD_RESET_LIFETIME,
        )
    )
    await db.flush()
    return IssuedAccountToken(user=user, token=raw_token)


async def reset_password(
    db: AsyncSession,
    *,
    raw_token: str,
    new_password: str,
    now: Optional[datetime] = None,
) -> Optional[User]:
    """Consume a valid reset token, replace the hash, and revoke all sessions."""

    new_password_hash = hash_password(new_password)
    checked_at = now or utcnow()
    token = await db.scalar(
        select(PasswordResetToken)
        .options(selectinload(PasswordResetToken.user))
        .where(
            PasswordResetToken.token_digest == digest_token(raw_token),
            PasswordResetToken.consumed_at.is_(None),
            PasswordResetToken.expires_at > checked_at,
        )
        .with_for_update()
    )
    if (
        token is None
        or token.user.state != UserState.ACTIVE.value
        or token.user.email_verified_at is None
    ):
        return None

    token.user.password_hash = new_password_hash
    token.consumed_at = checked_at
    await db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == token.user_id,
            PasswordResetToken.consumed_at.is_(None),
        )
        .values(consumed_at=checked_at)
    )
    await revoke_all_sessions(db, token.user_id, now=checked_at)
    await db.flush()
    return token.user
