#!/bin/bash

# Script para iniciar la aplicación completa (PostgreSQL + backend + frontend + scheduler).
# Valida prerrequisitos, espera a que cada servicio responda de verdad y guarda los PIDs
# para que stop.sh pueda detenerlos limpiamente.

set -euo pipefail

# --- Rutas (relativas al propio script, sin hardcodear el home) ---
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
RUN_DIR="$ROOT_DIR/.run"        # PIDs y estado
LOG_DIR="${LOG_DIR:-/tmp}"      # logs (override con LOG_DIR=...)

BACKEND_PORT=8000
FRONTEND_PORT=3000

mkdir -p "$RUN_DIR"

# --- Helpers de salida ---
info()  { echo "  $*"; }
ok()    { echo "✅ $*"; }
warn()  { echo "⚠️  $*"; }
fail()  { echo "❌ $*" >&2; exit 1; }
step()  { echo ""; echo "▶ $*"; }

# Espera hasta que un comando devuelva éxito, con timeout en segundos.
# Uso: wait_for <timeout> <descripción> <comando...>
wait_for() {
  local timeout=$1; shift
  local desc=$1; shift
  local elapsed=0
  until "$@" > /dev/null 2>&1; do
    if [ "$elapsed" -ge "$timeout" ]; then
      return 1
    fi
    sleep 1
    elapsed=$((elapsed + 1))
    printf "\r  esperando %s... %ds" "$desc" "$elapsed"
  done
  [ "$elapsed" -gt 0 ] && printf "\r%*s\r" 40 ""   # limpia la línea de progreso
  return 0
}

# ¿Sigue vivo el proceso de este PID?
alive() { kill -0 "$1" 2>/dev/null; }

echo "========================================="
echo " Iniciando Stock Analysis Platform"
echo "========================================="

# --- 0. Validar prerrequisitos ---
step "Validando prerrequisitos..."
command -v docker > /dev/null 2>&1 || fail "Docker no está instalado o no está en el PATH."
docker info > /dev/null 2>&1 || fail "Docker no está corriendo. Abrí Docker Desktop e intentá de nuevo."
[ -f "$BACKEND_DIR/venv/bin/activate" ] || fail "No existe el venv del backend en backend/venv. Creálo con: python -m venv backend/venv"
[ -d "$FRONTEND_DIR/node_modules" ] || warn "frontend/node_modules no existe; puede que necesites 'npm install' en frontend/."
ok "Prerrequisitos OK"

# --- 1. Detener instancias previas ---
step "Deteniendo instancias previas..."
pkill -f "uvicorn app.main:app" 2>/dev/null || true
pkill -f "next dev" 2>/dev/null || true
pkill -f "app/data/scheduler.py" 2>/dev/null || true
sleep 2
ok "Limpieza completa"

# --- 2. PostgreSQL ---
step "Iniciando PostgreSQL (Docker)..."
cd "$ROOT_DIR"
docker-compose up -d postgres
if ! wait_for 60 "PostgreSQL" docker-compose exec -T postgres pg_isready -U postgres; then
  fail "PostgreSQL no quedó listo a tiempo. Revisá: docker-compose logs postgres"
fi
ok "PostgreSQL listo"

# --- 3. Backend ---
step "Iniciando backend en http://localhost:$BACKEND_PORT ..."
cd "$BACKEND_DIR"
# shellcheck disable=SC1091
source venv/bin/activate
nohup python -m uvicorn app.main:app --reload --host 0.0.0.0 --port "$BACKEND_PORT" \
  > "$LOG_DIR/backend.log" 2>&1 &
BACKEND_PID=$!
echo "$BACKEND_PID" > "$RUN_DIR/backend.pid"

if ! wait_for 40 "backend /health" curl -sf "http://localhost:$BACKEND_PORT/health"; then
  alive "$BACKEND_PID" || fail "El backend murió al arrancar. Revisá: tail -n 50 $LOG_DIR/backend.log"
  fail "El backend no respondió en /health a tiempo. Revisá: tail -n 50 $LOG_DIR/backend.log"
fi
ok "Backend listo (PID $BACKEND_PID)"

# --- 4. Frontend ---
step "Iniciando frontend en http://localhost:$FRONTEND_PORT ..."
cd "$FRONTEND_DIR"
export NVM_DIR="$HOME/.nvm"
# shellcheck disable=SC1091
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
nohup npm run dev > "$LOG_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!
echo "$FRONTEND_PID" > "$RUN_DIR/frontend.pid"

if ! wait_for 60 "frontend" curl -sf "http://localhost:$FRONTEND_PORT"; then
  alive "$FRONTEND_PID" || fail "El frontend murió al arrancar. Revisá: tail -n 50 $LOG_DIR/frontend.log"
  warn "El frontend aún no responde, pero el proceso sigue vivo (Next puede tardar en compilar). Revisá: tail -f $LOG_DIR/frontend.log"
fi
ok "Frontend iniciado (PID $FRONTEND_PID)"

# --- 5. Scheduler ---
step "Iniciando scheduler..."
cd "$BACKEND_DIR"
PYTHONPATH="$BACKEND_DIR" nohup python app/data/scheduler.py \
  > "$LOG_DIR/scheduler.log" 2>&1 &
SCHEDULER_PID=$!
echo "$SCHEDULER_PID" > "$RUN_DIR/scheduler.pid"
sleep 2
if alive "$SCHEDULER_PID"; then
  ok "Scheduler iniciado (PID $SCHEDULER_PID)"
else
  warn "El scheduler no quedó vivo. Revisá: tail -n 50 $LOG_DIR/scheduler.log"
fi

# --- Resumen ---
echo ""
echo "========================================="
echo " ✅ Aplicación iniciada"
echo "========================================="
echo " Backend:   http://localhost:$BACKEND_PORT  (docs en /docs)"
echo " Frontend:  http://localhost:$FRONTEND_PORT"
echo ""
echo " Logs:"
echo "   tail -f $LOG_DIR/backend.log"
echo "   tail -f $LOG_DIR/frontend.log"
echo "   tail -f $LOG_DIR/scheduler.log"
echo ""
echo " Para detener todo:  ./stop.sh"
echo "========================================="
