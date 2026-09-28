from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.models.base import Base


TOKEN_DIGEST_LENGTH = 64


def normalize_email(value: str) -> str:
    """Return the canonical form persisted for an account email address."""
    normalized = value.strip().casefold()
    if not normalized:
        raise ValueError("email must not be empty")
    return normalized


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserRole(str, Enum):
    USER = "user"
    ADMIN = "admin"


class UserState(str, Enum):
    PENDING_VERIFICATION = "pending_verification"
    ACTIVE = "active"
    DISABLED = "disabled"


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        String(16), nullable=False, default=UserRole.USER.value
    )
    state: Mapped[str] = mapped_column(
        String(32), nullable=False, default=UserState.PENDING_VERIFICATION.value
    )
    email_verified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    disabled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    profile: Mapped[UserProfile] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )
    sessions: Mapped[list[AuthSession]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    email_verification_tokens: Mapped[list[EmailVerificationToken]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    password_reset_tokens: Mapped[list[PasswordResetToken]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    journal_trades: Mapped[list["JournalTrade"]] = relationship(
        back_populates="owner", passive_deletes=True
    )

    __table_args__ = (
        CheckConstraint("role IN ('user', 'admin')", name="ck_users_role"),
        CheckConstraint(
            "state IN ('pending_verification', 'active', 'disabled')",
            name="ck_users_state",
        ),
        Index("ix_users_state", "state"),
    )

    def __init__(self, **kwargs: object) -> None:
        # SQLAlchemy column defaults run at INSERT time. Set the security-sensitive
        # defaults at construction time as well so an in-memory account can never
        # be mistaken for privileged or active before it is flushed.
        kwargs.setdefault("role", UserRole.USER)
        kwargs.setdefault("state", UserState.PENDING_VERIFICATION)
        super().__init__(**kwargs)

    @validates("email")
    def _normalize_email(self, _key: str, value: str) -> str:
        return normalize_email(value)

    def activate(self, now: Optional[datetime] = None) -> None:
        if self.state == UserState.DISABLED.value:
            raise ValueError("a disabled user cannot be activated")
        activated_at = now or _utcnow()
        self.state = UserState.ACTIVE.value
        self.email_verified_at = self.email_verified_at or activated_at

    def disable(self, now: Optional[datetime] = None) -> None:
        if self.state != UserState.DISABLED.value:
            self.state = UserState.DISABLED.value
            self.disabled_at = now or _utcnow()


class UserProfile(Base):
    __tablename__ = "user_profiles"

    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)

    user: Mapped[User] = relationship(back_populates="profile")

    __table_args__ = (
        CheckConstraint(
            "length(trim(display_name)) BETWEEN 1 AND 80",
            name="ck_user_profiles_display_name_length",
        ),
    )

    @validates("display_name")
    def _validate_display_name(self, _key: str, value: str) -> str:
        normalized = value.strip()
        if not 1 <= len(normalized) <= 80:
            raise ValueError("display_name must contain between 1 and 80 characters")
        return normalized


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_digest: Mapped[str] = mapped_column(
        String(TOKEN_DIGEST_LENGTH), nullable=False, unique=True
    )
    csrf_token_digest: Mapped[str] = mapped_column(
        String(TOKEN_DIGEST_LENGTH), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="sessions")

    __table_args__ = (
        CheckConstraint(
            "length(token_digest) = 64", name="ck_auth_sessions_token_digest_length"
        ),
        CheckConstraint(
            "length(csrf_token_digest) = 64",
            name="ck_auth_sessions_csrf_digest_length",
        ),
        Index("ix_auth_sessions_user_expires", "user_id", "expires_at"),
    )

    def is_expired(self, now: Optional[datetime] = None) -> bool:
        return self.expires_at <= (now or _utcnow())

    def is_active(self, now: Optional[datetime] = None) -> bool:
        return self.revoked_at is None and not self.is_expired(now)

    def revoke(self, now: Optional[datetime] = None) -> None:
        self.revoked_at = self.revoked_at or now or _utcnow()


class _SingleUseToken:
    expires_at: datetime
    consumed_at: Optional[datetime]

    def is_expired(self, now: Optional[datetime] = None) -> bool:
        return self.expires_at <= (now or _utcnow())

    def is_usable(self, now: Optional[datetime] = None) -> bool:
        return self.consumed_at is None and not self.is_expired(now)

    def consume(self, now: Optional[datetime] = None) -> bool:
        consumed_at = now or _utcnow()
        if not self.is_usable(consumed_at):
            return False
        self.consumed_at = consumed_at
        return True


class EmailVerificationToken(_SingleUseToken, Base):
    __tablename__ = "email_verification_tokens"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_digest: Mapped[str] = mapped_column(
        String(TOKEN_DIGEST_LENGTH), nullable=False, unique=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped[User] = relationship(back_populates="email_verification_tokens")

    __table_args__ = (
        CheckConstraint(
            "length(token_digest) = 64",
            name="ck_email_verification_tokens_digest_length",
        ),
        Index("ix_email_verification_tokens_user_expires", "user_id", "expires_at"),
    )


class PasswordResetToken(_SingleUseToken, Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_digest: Mapped[str] = mapped_column(
        String(TOKEN_DIGEST_LENGTH), nullable=False, unique=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped[User] = relationship(back_populates="password_reset_tokens")

    __table_args__ = (
        CheckConstraint(
            "length(token_digest) = 64", name="ck_password_reset_tokens_digest_length"
        ),
        Index("ix_password_reset_tokens_user_expires", "user_id", "expires_at"),
    )


# Register the journal side of User.journal_trades when identity models are
# imported in isolation (CLI commands and focused auth tests do this).
from app.models import stock as _stock_models  # noqa: E402,F401
