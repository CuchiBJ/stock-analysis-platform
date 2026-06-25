#!/bin/bash

# Detiene los servicios iniciados por start.sh usando los PIDs guardados en .run/.
# Cae a pkill por patrón como respaldo. Con --postgres también baja el contenedor.

set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="$ROOT_DIR/.run"

STOP_POSTGRES=0
[ "${1:-}" = "--postgres" ] && STOP_POSTGRES=1

echo "▶ Deteniendo Stock Analysis Platform..."

# Mata el proceso de un .pid file (y espera a que termine; SIGKILL si se resiste).
stop_pid_file() {
  local name=$1
  local file="$RUN_DIR/$name.pid"
  [ -f "$file" ] || return 0
  local pid
  pid="$(cat "$file")"
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null
    for _ in 1 2 3 4 5; do
      kill -0 "$pid" 2>/dev/null || break
      sleep 1
    done
    kill -9 "$pid" 2>/dev/null || true
    echo "  ✅ $name detenido (PID $pid)"
  else
    echo "  • $name no estaba corriendo"
  fi
  rm -f "$file"
}

stop_pid_file backend
stop_pid_file frontend
stop_pid_file scheduler

# Respaldo por si quedaron procesos huérfanos (sin .pid).
pkill -f "uvicorn app.main:app" 2>/dev/null && echo "  ✅ uvicorn residual detenido" || true
pkill -f "next dev" 2>/dev/null && echo "  ✅ next dev residual detenido" || true
pkill -f "app/data/scheduler.py" 2>/dev/null && echo "  ✅ scheduler residual detenido" || true

if [ "$STOP_POSTGRES" -eq 1 ]; then
  echo "▶ Deteniendo PostgreSQL (Docker)..."
  (cd "$ROOT_DIR" && docker-compose stop postgres) && echo "  ✅ PostgreSQL detenido"
else
  echo "  • PostgreSQL sigue corriendo (usá './stop.sh --postgres' para bajarlo)"
fi

echo "✅ Listo."
