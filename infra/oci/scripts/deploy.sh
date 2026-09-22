#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${ROOT_DIR:-/opt/stock-analysis}"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT_DIR/compose.production.yml}"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env.production}"

cd "$ROOT_DIR"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE. Copy .env.production.example and fill every required value." >&2
  exit 1
fi

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" config --quiet
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" build --pull api scheduler migrate
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --remove-orphans

api_container="$(docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps -q api)"
for _ in $(seq 1 36); do
  status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$api_container")"
  [[ "$status" == "healthy" ]] && break
  [[ "$status" == "unhealthy" || "$status" == "exited" ]] && {
    docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" logs --tail=100 api
    exit 1
  }
  sleep 5
done

test "$(docker inspect --format '{{.State.Health.Status}}' "$api_container")" = "healthy"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps
