#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 /absolute/path/to/backup.dump" >&2
  exit 2
fi

ROOT_DIR="${ROOT_DIR:-/opt/stock-analysis}"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT_DIR/compose.production.yml}"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env.production}"
BACKUP_FILE="$1"
RESTORE_ALEMBIC_TARGET="${RESTORE_ALEMBIC_TARGET:-head}"
RESTORE_START_SERVICES="${RESTORE_START_SERVICES:-true}"

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

if [[ ! -s "$BACKUP_FILE" ]]; then
  echo "Backup does not exist or is empty: $BACKUP_FILE" >&2
  exit 1
fi

echo "This restores into the configured database and replaces conflicting objects."
read -r -p "Type RESTORE to continue: " confirmation
[[ "$confirmation" == "RESTORE" ]] || exit 1

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" stop api scheduler
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T postgres \
  pg_restore --clean --if-exists --no-owner --no-acl \
  --username "${POSTGRES_USER:-stock_app}" \
  --dbname "${POSTGRES_DB:-stock_analysis}" < "$BACKUP_FILE"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" run --rm migrate \
  alembic upgrade "$RESTORE_ALEMBIC_TARGET"

if [[ "$RESTORE_START_SERVICES" == "true" ]]; then
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d api scheduler caddy
else
  echo "Restore complete; application services remain stopped for maintenance."
fi
