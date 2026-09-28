"""Provider-neutral account email delivery.

The development adapter intentionally captures messages only in memory.  It
does not log message bodies or action URLs, and captured URLs are excluded from
object representations to reduce accidental token disclosure in diagnostics.
"""

from __future__ import annotations

import asyncio
import html
import smtplib
import ssl
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import formataddr
from enum import Enum
from typing import Protocol, runtime_checkable
from urllib.parse import urlencode, urlsplit

from app.core.config import Settings, settings
from app.services.security_events import record_security_event


class MailConfigurationError(RuntimeError):
    """Raised when account-email configuration is invalid or incomplete."""


class EmailKind(str, Enum):
    VERIFICATION = "verification"
    PASSWORD_RESET = "password_reset"


@runtime_checkable
class Mailer(Protocol):
    async def send_verification_email(
        self, *, recipient: str, verification_url: str
    ) -> None:
        """Deliver an email-address verification link."""
        ...

    async def send_password_reset_email(
        self, *, recipient: str, reset_url: str
    ) -> None:
        """Deliver a password-reset link."""
        ...


@dataclass(frozen=True)
class CapturedEmail:
    recipient: str
    kind: EmailKind
    subject: str
    action_url: str = field(repr=False)


class CaptureMailer:
    """In-memory development/test mailer that never logs raw action tokens."""

    def __init__(self) -> None:
        self._messages: list[CapturedEmail] = []

    @property
    def messages(self) -> tuple[CapturedEmail, ...]:
        return tuple(self._messages)

    def clear(self) -> None:
        self._messages.clear()

    async def send_verification_email(
        self, *, recipient: str, verification_url: str
    ) -> None:
        self._messages.append(
            CapturedEmail(
                recipient=_validate_recipient(recipient),
                kind=EmailKind.VERIFICATION,
                subject="Verify your email address",
                action_url=_validate_action_url(verification_url),
            )
        )
        record_security_event(
            "mail_delivery", "success", reason="verification"
        )

    async def send_password_reset_email(
        self, *, recipient: str, reset_url: str
    ) -> None:
        self._messages.append(
            CapturedEmail(
                recipient=_validate_recipient(recipient),
                kind=EmailKind.PASSWORD_RESET,
                subject="Reset your password",
                action_url=_validate_action_url(reset_url),
            )
        )
        record_security_event(
            "mail_delivery", "success", reason="password_reset"
        )


class DisabledMailer:
    """Fail-closed adapter used only when every public account flow is disabled."""

    async def send_verification_email(
        self, *, recipient: str, verification_url: str
    ) -> None:
        raise MailConfigurationError("public account email delivery is disabled")

    async def send_password_reset_email(
        self, *, recipient: str, reset_url: str
    ) -> None:
        raise MailConfigurationError("public account email delivery is disabled")


class SMTPMailer:
    """SMTP adapter whose blocking network work runs outside the event loop."""

    def __init__(self, app_settings: Settings = settings) -> None:
        _validate_smtp_settings(app_settings, require_credentials=False)
        self._settings = app_settings

    async def send_verification_email(
        self, *, recipient: str, verification_url: str
    ) -> None:
        message = self._build_message(
            recipient=recipient,
            subject="Verify your email address",
            intro="Confirm your email address to activate your account.",
            action_label="Verify email",
            action_url=verification_url,
        )
        await self._deliver(message, reason="verification")

    async def send_password_reset_email(
        self, *, recipient: str, reset_url: str
    ) -> None:
        message = self._build_message(
            recipient=recipient,
            subject="Reset your password",
            intro="Use this link to choose a new password.",
            action_label="Reset password",
            action_url=reset_url,
        )
        await self._deliver(message, reason="password_reset")

    async def _deliver(self, message: EmailMessage, *, reason: str) -> None:
        try:
            await asyncio.to_thread(self._send_blocking, message)
        except Exception:
            record_security_event(
                "mail_delivery", "failure", reason="smtp_error"
            )
            raise
        record_security_event("mail_delivery", "success", reason=reason)

    def _build_message(
        self,
        *,
        recipient: str,
        subject: str,
        intro: str,
        action_label: str,
        action_url: str,
    ) -> EmailMessage:
        safe_recipient = _validate_recipient(recipient)
        safe_url = _validate_action_url(action_url)
        sender_email = self._settings.smtp_from_email
        if sender_email is None:  # Guarded by constructor validation.
            raise MailConfigurationError("SMTP sender is not configured")

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = formataddr(
            (_validate_header(self._settings.smtp_from_name), sender_email)
        )
        message["To"] = safe_recipient
        message.set_content(f"{intro}\n\n{safe_url}\n")
        message.add_alternative(
            "<p>{intro}</p><p><a href=\"{url}\">{label}</a></p>".format(
                intro=html.escape(intro),
                url=html.escape(safe_url, quote=True),
                label=html.escape(action_label),
            ),
            subtype="html",
        )
        return message

    def _send_blocking(self, message: EmailMessage) -> None:
        host = self._settings.smtp_host
        if host is None:  # Guarded by constructor validation.
            raise MailConfigurationError("SMTP host is not configured")

        context = ssl.create_default_context()
        if self._settings.smtp_use_ssl:
            smtp_factory = smtplib.SMTP_SSL
            smtp_kwargs = {"context": context}
        else:
            smtp_factory = smtplib.SMTP
            smtp_kwargs = {}

        with smtp_factory(
            host,
            self._settings.smtp_port,
            timeout=self._settings.smtp_timeout_seconds,
            **smtp_kwargs,
        ) as smtp:
            if self._settings.smtp_use_starttls:
                smtp.starttls(context=context)
            if self._settings.smtp_username:
                smtp.login(
                    self._settings.smtp_username,
                    self._settings.smtp_password or "",
                )
            smtp.send_message(message)


def create_mailer(app_settings: Settings = settings) -> Mailer:
    """Construct the configured mail adapter without performing network I/O."""
    backend = app_settings.mailer_backend.strip().casefold()
    if backend == "capture":
        return CaptureMailer()
    if backend == "disabled":
        return DisabledMailer()
    if backend == "smtp":
        return SMTPMailer(app_settings)
    raise MailConfigurationError(
        "MAILER_BACKEND must be 'capture', 'disabled', or 'smtp'"
    )


def build_verification_url(
    raw_token: str, app_settings: Settings = settings
) -> str:
    return _build_public_action_url("/verify-email", raw_token, app_settings)


def build_password_reset_url(
    raw_token: str, app_settings: Settings = settings
) -> str:
    return _build_public_action_url("/reset-password", raw_token, app_settings)


def validate_production_mail_settings(app_settings: Settings = settings) -> None:
    """Fail startup when production public-auth mail settings are unsafe."""
    environment = app_settings.app_environment.strip().casefold()
    if environment not in {"prod", "production"}:
        return

    parsed_base_url = _parse_public_base_url(app_settings.public_base_url)
    if parsed_base_url.scheme != "https":
        raise MailConfigurationError("PUBLIC_BASE_URL must use HTTPS in production")
    if parsed_base_url.hostname in {"localhost", "127.0.0.1", "::1"}:
        raise MailConfigurationError(
            "PUBLIC_BASE_URL must use a public hostname in production"
        )
    backend = app_settings.mailer_backend.strip().casefold()
    if not app_settings.auth_public_account_flows_enabled:
        if backend != "disabled":
            raise MailConfigurationError(
                "MAILER_BACKEND must be 'disabled' when public account flows are disabled"
            )
        return
    if backend != "smtp":
        raise MailConfigurationError("MAILER_BACKEND must be 'smtp' in production")
    _validate_smtp_settings(app_settings, require_credentials=True)


def _build_public_action_url(
    path: str, raw_token: str, app_settings: Settings
) -> str:
    if not isinstance(raw_token, str) or not raw_token:
        raise ValueError("action token must not be empty")
    parsed = _parse_public_base_url(app_settings.public_base_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    base_path = parsed.path.rstrip("/")
    return f"{origin}{base_path}{path}?{urlencode({'token': raw_token})}"


def _parse_public_base_url(value: str):
    parsed = urlsplit(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise MailConfigurationError("PUBLIC_BASE_URL must be an absolute HTTP(S) URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise MailConfigurationError(
            "PUBLIC_BASE_URL must not contain credentials, query, or fragment"
        )
    return parsed


def _validate_smtp_settings(
    app_settings: Settings, *, require_credentials: bool
) -> None:
    if not app_settings.smtp_host or not app_settings.smtp_host.strip():
        raise MailConfigurationError("SMTP_HOST is required for SMTP delivery")
    if not app_settings.smtp_from_email:
        raise MailConfigurationError("SMTP_FROM_EMAIL is required for SMTP delivery")
    _validate_recipient(app_settings.smtp_from_email)
    if app_settings.smtp_use_ssl and app_settings.smtp_use_starttls:
        raise MailConfigurationError(
            "SMTP_USE_SSL and SMTP_USE_STARTTLS cannot both be enabled"
        )
    has_username = bool(app_settings.smtp_username)
    has_password = bool(app_settings.smtp_password)
    if has_username != has_password:
        raise MailConfigurationError(
            "SMTP_USERNAME and SMTP_PASSWORD must be configured together"
        )
    if require_credentials and not (has_username and has_password):
        raise MailConfigurationError("SMTP credentials are required in production")
    if require_credentials and not (
        app_settings.smtp_use_ssl or app_settings.smtp_use_starttls
    ):
        raise MailConfigurationError("encrypted SMTP transport is required in production")


def _validate_recipient(value: str) -> str:
    candidate = _validate_header(value).strip()
    local, separator, domain = candidate.rpartition("@")
    if not separator or not local or not domain or "." not in domain:
        raise ValueError("recipient must be a valid email address")
    return candidate


def _validate_header(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("email header value must not be empty")
    if "\r" in value or "\n" in value:
        raise ValueError("email header value contains a line break")
    return value.strip()


def _validate_action_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("action URL must be an absolute HTTP(S) URL")
    return value


__all__ = [
    "CaptureMailer",
    "CapturedEmail",
    "DisabledMailer",
    "EmailKind",
    "Mailer",
    "MailConfigurationError",
    "SMTPMailer",
    "build_password_reset_url",
    "build_verification_url",
    "create_mailer",
    "validate_production_mail_settings",
]
