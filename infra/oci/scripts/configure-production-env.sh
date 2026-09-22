#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 || $# -gt 3 ]]; then
  echo "Usage: $0 /path/to/source.env API_DOMAIN [CORS_ORIGINS]" >&2
  exit 2
fi

SOURCE_ENV="$1"
API_DOMAIN="$2"
CORS_ORIGINS="${3:-http://localhost:3000}"
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

if [[ -z "${POLYGON_API_KEY:-}" ]]; then
  echo "POLYGON_API_KEY is missing from $SOURCE_ENV" >&2
  exit 1
fi

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
