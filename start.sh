#!/bin/bash

# Script para iniciar la aplicación completa (backend + frontend)

echo "Iniciando Stock Analysis Platform..."

# Matar instancias existentes
echo "Verificando instancias existentes..."
pkill -f "uvicorn app.main:app" 2>/dev/null
pkill -f "next dev" 2>/dev/null
sleep 2

# Iniciar base de datos PostgreSQL
echo "Iniciando PostgreSQL con Docker..."
cd /Users/fernandocucchiarelli/CascadeProjects/windsurf-project/stock-analysis-platform
docker-compose up -d postgres
echo "Esperando que PostgreSQL esté listo..."
until docker-compose exec -T postgres pg_isready -U postgres > /dev/null 2>&1; do
  sleep 1
done
echo "PostgreSQL listo!"

# Iniciar backend
echo "Iniciando backend en http://localhost:8000..."
cd /Users/fernandocucchiarelli/CascadeProjects/windsurf-project/stock-analysis-platform/backend
source venv/bin/activate
nohup python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 > /tmp/backend.log 2>&1 &
BACKEND_PID=$!
echo "Backend iniciado (PID: $BACKEND_PID)"

# Esperar unos segundos para que el backend inicie
sleep 3

# Iniciar frontend
echo "Iniciando frontend en http://localhost:3000..."
cd /Users/fernandocucchiarelli/CascadeProjects/windsurf-project/stock-analysis-platform/frontend
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
nohup npm run dev > /tmp/frontend.log 2>&1 &
FRONTEND_PID=$!
echo "Frontend iniciado (PID: $FRONTEND_PID)"

# Esperar unos segundos para que el frontend inicie
sleep 5

# Iniciar scheduler
echo "Iniciando scheduler automático..."
cd /Users/fernandocucchiarelli/CascadeProjects/windsurf-project/stock-analysis-platform/backend
source venv/bin/activate
PYTHONPATH=/Users/fernandocucchiarelli/CascadeProjects/windsurf-project/stock-analysis-platform/backend nohup python app/data/scheduler.py > /tmp/scheduler.log 2>&1 &
SCHEDULER_PID=$!
echo "Scheduler iniciado (PID: $SCHEDULER_PID)"

echo ""
echo "========================================="
echo "Aplicación iniciada correctamente!"
echo "========================================="
echo "Backend: http://localhost:8000"
echo "Frontend: http://localhost:3000"
echo "Backend PID: $BACKEND_PID"
echo "Frontend PID: $FRONTEND_PID"
echo "Scheduler PID: $SCHEDULER_PID"
echo ""
echo "Logs:"
echo "  Backend: tail -f /tmp/backend.log"
echo "  Frontend: tail -f /tmp/frontend.log"
echo "  Scheduler: tail -f /tmp/scheduler.log"
echo ""
echo "Para detener:"
echo "  kill $BACKEND_PID $FRONTEND_PID $SCHEDULER_PID"
echo "========================================="
