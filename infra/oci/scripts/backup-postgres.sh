#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${ROOT_DIR:-/opt/stock-analysis}"
BACKUP_DIR="${BACKUP_DIR:-$ROOT_DIR/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT_DIR/compose.production.yml}"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env.production}"

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

mkdir -p "$BACKUP_DIR"
umask 077

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
target="$BACKUP_DIR/stock_analysis_$timestamp.dump"

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T postgres \
  pg_dump --format=custom --no-owner --no-acl \
  --username "${POSTGRES_USER:-stock_app}" \
  --dbname "${POSTGRES_DB:-stock_analysis}" > "$target"

test -s "$target"
find "$BACKUP_DIR" -type f -name 'stock_analysis_*.dump' -mtime "+$RETENTION_DAYS" -delete
echo "Backup created: $target"
