from typing import Optional

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    app_environment: str = Field("development", env="APP_ENVIRONMENT")
    database_url: str = Field(..., env="DATABASE_URL")
    polygon_api_key: str = Field(..., env="POLYGON_API_KEY")
    cors_origins: str = Field("http://localhost:3000", env="CORS_ORIGINS")
    redis_url: str = Field("redis://localhost:6379/0", env="REDIS_URL")

    # Public account links and mail delivery. Development captures messages in
    # memory; production requires HTTPS and either disabled public flows or SMTP.
    public_base_url: str = Field("http://localhost:3000", env="PUBLIC_BASE_URL")
    auth_public_account_flows_enabled: bool = Field(
        True, env="AUTH_PUBLIC_ACCOUNT_FLOWS_ENABLED"
    )
    mailer_backend: str = Field("capture", env="MAILER_BACKEND")
    smtp_host: Optional[str] = Field(None, env="SMTP_HOST")
    smtp_port: int = Field(587, ge=1, le=65535, env="SMTP_PORT")
    smtp_username: Optional[str] = Field(None, env="SMTP_USERNAME")
    smtp_password: Optional[str] = Field(None, env="SMTP_PASSWORD")
    smtp_from_email: Optional[str] = Field(None, env="SMTP_FROM_EMAIL")
    smtp_from_name: str = Field("Stock Analysis Platform", env="SMTP_FROM_NAME")
    smtp_use_starttls: bool = Field(True, env="SMTP_USE_STARTTLS")
    smtp_use_ssl: bool = Field(False, env="SMTP_USE_SSL")
    smtp_timeout_seconds: float = Field(
        10.0, gt=0, env="SMTP_TIMEOUT_SECONDS"
    )

    # Authentication rate limits use one fixed window per source and normalized
    # email.  Keeping the values separate lets operators tune high-volume login
    # traffic without weakening the lower-volume email flows.
    auth_rate_limit_window_seconds: int = Field(
        60, ge=1, env="AUTH_RATE_LIMIT_WINDOW_SECONDS"
    )
    auth_rate_limit_registration_source: int = Field(
        10, ge=1, env="AUTH_RATE_LIMIT_REGISTRATION_SOURCE"
    )
    auth_rate_limit_registration_email: int = Field(
        3, ge=1, env="AUTH_RATE_LIMIT_REGISTRATION_EMAIL"
    )
    auth_rate_limit_login_source: int = Field(
        30, ge=1, env="AUTH_RATE_LIMIT_LOGIN_SOURCE"
    )
    auth_rate_limit_login_email: int = Field(
        10, ge=1, env="AUTH_RATE_LIMIT_LOGIN_EMAIL"
    )
    auth_rate_limit_verification_resend_source: int = Field(
        10, ge=1, env="AUTH_RATE_LIMIT_VERIFICATION_RESEND_SOURCE"
    )
    auth_rate_limit_verification_resend_email: int = Field(
        3, ge=1, env="AUTH_RATE_LIMIT_VERIFICATION_RESEND_EMAIL"
    )
    auth_rate_limit_recovery_source: int = Field(
        10, ge=1, env="AUTH_RATE_LIMIT_RECOVERY_SOURCE"
    )
    auth_rate_limit_recovery_email: int = Field(
        3, ge=1, env="AUTH_RATE_LIMIT_RECOVERY_EMAIL"
    )
    auth_rate_limit_fail_open: bool = Field(
        False, env="AUTH_RATE_LIMIT_FAIL_OPEN"
    )

    # Anthropic API key for the in-app chat (read-only DB Q&A via tool use).
    anthropic_api_key: Optional[str] = Field(None, env="ANTHROPIC_API_KEY")

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
