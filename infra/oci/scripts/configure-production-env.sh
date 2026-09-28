#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 || $# -gt 3 ]]; then
  echo "Usage: $0 /path/to/source.env API_DOMAIN [CORS_ORIGINS]" >&2
  exit 2
fi

SOURCE_ENV="$1"
API_DOMAIN="$2"
CORS_ORIGINS="${3:-https://$API_DOMAIN}"
ROOT_DIR="${ROOT_DIR:-/opt/stock-analysis}"
TARGET_ENV="$ROOT_DIR/.env.production"

if [[ ! -r "$SOURCE_ENV" ]]; then
  echo "Cannot read source env: $SOURCE_ENV" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$SOURCE_ENV"
set +a

public_account_flows_enabled="${AUTH_PUBLIC_ACCOUNT_FLOWS_ENABLED:-false}"
case "$public_account_flows_enabled" in
  true|false) ;;
  *)
    echo "AUTH_PUBLIC_ACCOUNT_FLOWS_ENABLED must be true or false" >&2
    exit 1
    ;;
esac

required_names=(POLYGON_API_KEY)
if [[ "$public_account_flows_enabled" == "true" ]]; then
  required_names+=(SMTP_HOST SMTP_USERNAME SMTP_PASSWORD SMTP_FROM_EMAIL)
fi
for required_name in "${required_names[@]}"; do
  if [[ -z "${!required_name:-}" ]]; then
    echo "$required_name is missing from $SOURCE_ENV" >&2
    exit 1
  fi
done

postgres_password="$(openssl rand -hex 32)"
temporary_env="$(mktemp "$ROOT_DIR/.env.production.XXXXXX")"
trap 'rm -f "$temporary_env"' EXIT
umask 077

{
  printf 'POSTGRES_DB=stock_analysis\n'
  printf 'POSTGRES_USER=stock_app\n'
  printf 'POSTGRES_PASSWORD=%s\n' "$postgres_password"
  printf 'DATABASE_URL=postgresql+asyncpg://stock_app:%s@postgres:5432/stock_analysis\n' "$postgres_password"
  printf 'REDIS_URL=redis://redis:6379/0\n'
  printf 'APP_ENVIRONMENT=production\n'
  printf 'PUBLIC_BASE_URL=https://%s\n' "$API_DOMAIN"
  printf 'AUTH_PUBLIC_ACCOUNT_FLOWS_ENABLED=%s\n' "$public_account_flows_enabled"
  if [[ "$public_account_flows_enabled" == "true" ]]; then
    printf 'MAILER_BACKEND=smtp\n'
  else
    printf 'MAILER_BACKEND=disabled\n'
  fi
  printf 'SMTP_HOST=%s\n' "${SMTP_HOST:-}"
  printf 'SMTP_PORT=%s\n' "${SMTP_PORT:-587}"
  printf 'SMTP_USERNAME=%s\n' "${SMTP_USERNAME:-}"
  printf 'SMTP_PASSWORD=%s\n' "${SMTP_PASSWORD:-}"
  printf 'SMTP_FROM_EMAIL=%s\n' "${SMTP_FROM_EMAIL:-}"
  printf 'SMTP_FROM_NAME=%q\n' "${SMTP_FROM_NAME:-Stock Analysis Platform}"
  printf 'SMTP_USE_STARTTLS=%s\n' "${SMTP_USE_STARTTLS:-true}"
  printf 'SMTP_USE_SSL=%s\n' "${SMTP_USE_SSL:-false}"
  printf 'SMTP_TIMEOUT_SECONDS=%s\n' "${SMTP_TIMEOUT_SECONDS:-10}"
  printf 'AUTH_RATE_LIMIT_FAIL_OPEN=false\n'
  printf 'POLYGON_API_KEY=%s\n' "$POLYGON_API_KEY"
  printf 'ANTHROPIC_API_KEY=%s\n' "${ANTHROPIC_API_KEY:-}"
  printf 'IBKR_FLEX_TOKEN=%s\n' "${IBKR_FLEX_TOKEN:-}"
  printf 'IBKR_FLEX_QUERY_ID=%s\n' "${IBKR_FLEX_QUERY_ID:-}"
  printf 'CORS_ORIGINS=%s\n' "$CORS_ORIGINS"
  printf 'API_DOMAIN=%s\n' "$API_DOMAIN"
} > "$temporary_env"

chmod 0600 "$temporary_env"
mv "$temporary_env" "$TARGET_ENV"
trap - EXIT
echo "Created $TARGET_ENV with mode 0600"
