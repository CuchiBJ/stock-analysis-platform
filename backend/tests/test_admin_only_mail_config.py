from types import SimpleNamespace

import pytest

from app.services.mailer import (
    DisabledMailer,
    MailConfigurationError,
    create_mailer,
    validate_production_mail_settings,
)


def _settings(**overrides):
    values = {
        "app_environment": "production",
        "public_base_url": "https://129-159-125-184.sslip.io",
        "auth_public_account_flows_enabled": False,
        "mailer_backend": "disabled",
        "smtp_host": None,
        "smtp_port": 587,
        "smtp_username": None,
        "smtp_password": None,
        "smtp_from_email": None,
        "smtp_from_name": "Stock Analysis Platform",
        "smtp_use_starttls": True,
        "smtp_use_ssl": False,
        "smtp_timeout_seconds": 10,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_production_admin_only_mode_accepts_public_https_without_smtp():
    settings = _settings()

    validate_production_mail_settings(settings)

    assert isinstance(create_mailer(settings), DisabledMailer)


def test_admin_only_mode_requires_explicit_disabled_mailer():
    with pytest.raises(MailConfigurationError, match="must be 'disabled'"):
        validate_production_mail_settings(_settings(mailer_backend="capture"))


def test_public_account_flows_still_require_complete_smtp():
    with pytest.raises(MailConfigurationError, match="must be 'smtp'"):
        validate_production_mail_settings(
            _settings(auth_public_account_flows_enabled=True)
        )
