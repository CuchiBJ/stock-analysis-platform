## Why

Hoy 3 bugs sucedieron silenciosos por días: DISTINCT ON quebrado nightly, str/Date mismatch matando SLOW, lookback de 3 días dejando /live vacío post-Memorial Day. Cada uno detectado solo cuando Fernando notó "los datos están viejos". Patrón estructural:

1. `asyncio.create_task` swallow exceptions → errores van a `Task exception was never retrieved` que termina en logs que nadie lee
2. La UI renderiza `stock_metrics.date = 2026-05-22` con la misma confianza que data fresh — sin distinción visual
3. Sin invariante "después de SLOW, ¿avanzó la fecha?" — un cycle fallado se ve idéntico a uno exitoso

El fix no es otro patch. Es una capa de "data health" que hace **imposible** ignorar el próximo fail.

## What Changes

- **NEW table** `scheduler_errors` con `(task_name, exception_type, message, traceback, occurred_at, resolved)` — migración Alembic
- **NEW** `app/services/task_error_tracker.py` con decorator `@track_task_errors` que envuelve async functions: si raise → log ERROR + persiste a `scheduler_errors`. Reemplaza el patrón "fire-and-forget que muere silencioso"
- **MODIFIED** `app/data/scheduler.py` — aplicar el decorator a los 8 task entrypoints (`_evaluate_pending_outcomes`, `_batch_scan_transitions`, `_run_realtime_discovery`, `_run_discovery_scans`, `_reevaluate_tiers`, `_run_health_check`, `_run_lifecycle_tracking`, `_broadcast_metrics_updated`)
- **NEW endpoint** `GET /api/v1/health/data-freshness` retornando:
  ```json
  {
    "as_of": "<utc>",
    "stock_metrics_latest": "<date>",
    "stock_price_latest": "<date>",
    "metrics_lag_days": <int>,
    "is_stale": <bool>,
    "today_et": "<date>",
    "is_weekday": <bool>,
    "recent_errors_24h": <int>,
    "recent_errors": [{task_name, type, message, occurred_at} ...],
    "warnings": [<str>...]
  }
  ```
  `is_stale = (metrics_lag_days > 0)` (metrics quedó detrás de precios = SLOW falló). Más signal que "metrics.date < today" porque tolera weekends/holidays naturalmente.
- **NEW frontend** `DataHealthBanner` en `DashboardLayout` que polea cada 60s y muestra:
  - **Rojo** si `recent_errors_24h > 0`: "X errores en el scheduler · ver detalles"
  - **Amber** si `is_stale`: "Métricas atrás por X días vs precios · SLOW no completó"
  - **Hidden** si todo OK
- Banner NO es dismissible. Stale data debe ser imposible de olvidar.
- **NEW script** `backend/scripts/health_check.py` standalone que imprime el mismo health snapshot — corre via cron/CI/manual

## Capabilities

### New Capabilities
- `data-health-monitoring` — visibilidad continua del estado del pipeline de datos + captura de errores async

### Modified Capabilities
- (none) — el resto del stack no cambia

## Impact

- NEW: `backend/alembic/versions/<id>_add_scheduler_errors.py`
- NEW: `backend/app/models/scheduler.py` (or extend stock.py — TBD)
- NEW: `backend/app/services/task_error_tracker.py`
- NEW: `backend/app/api/v1/endpoints/health.py`
- NEW: `backend/scripts/health_check.py`
- NEW: `frontend/components/layout/DataHealthBanner.tsx`
- MODIFIED: `backend/app/data/scheduler.py` (apply decorator)
- MODIFIED: `backend/app/api/v1/api.py` (register router)
- MODIFIED: `frontend/components/layout/DashboardLayout.tsx` (mount banner)

## Non-goals

- No alerting externo (Slack/email). Phase 1 es visual + log persistente. Si el operador no abre la app, no se entera. Aceptable porque ya pasa eso hoy.
- No tracking del proceso del scheduler en sí (heartbeat). Si data está fresh, scheduler está vivo. Si está stale, el banner aparece independiente de la causa raíz.
- No resolución automática de errores (`resolved=true` queda manual por ahora — un endpoint POST de "marcar como resuelto" puede venir después).
- No tests unitarios del decorator. Logic trivial, integración cubre.
- No UI de detalle de errores Phase 1. El banner muestra count + tipo del más reciente; investigación va a logs/DB directo.
- No replicar `track_task_errors` en endpoints HTTP. El gap es `create_task`, no las requests (que ya tienen logging por FastAPI).
