## Why

Hoy `DataHealthBanner` sólo aparece cuando algo está stale o errored — el operador no tiene forma de saber, mirando la app, **cuán fresco y completo** está el snapshot que está leyendo en este instante. Ejemplos del gap:

- A las 09:35 ET el régimen acaba de recalcular con prices de los primeros 60 segundos de mercado, pero no hay nada en la UI que lo señale (ver conversación previa sobre confiabilidad del market engine en la primera hora).
- Una SLOW corre 30 min y procesa sólo 4000 de 6600 símbolos (errores de Polygon en un lote): el banner no se enciende porque `is_stale=false` (la fecha más reciente sigue siendo hoy), pero el universo está incompleto.
- El operador no ve `last_price_update_at` ni `last_slow_metrics_at` — son variables en memoria del scheduler ([scheduler.py:329-332](../../../backend/app/data/scheduler.py#L329-L332)), no se persisten.

Esto erosiona el principio #6 (Operational clarity > feature richness): el sistema "miente por omisión" cuando los datos están parcialmente frescos.

## What Changes

- **Persistir heartbeats del scheduler**: nueva tabla `pipeline_heartbeats` con una fila por ciclo (`price`, `fast_metrics`, `slow_metrics`, `realtime_discovery`, `post_close_cycle`). Se actualiza al final de cada ciclo con `last_run_at`, `last_success_at`, `last_duration_seconds`, `symbols_processed`, `symbols_expected`, `status` (`ok`/`partial`/`failed`).
- **Extender `/api/v1/health/data-freshness`**: agregar `pipeline_heartbeats` (lista), `coverage` (`{expected, actual, pct}` para la universe quality del día), `market_state` (`{is_open, is_warmup, minutes_since_open, session_phase}`). Sin breaking changes — campos existentes se mantienen.
- **Frontend always-on chip**: nuevo componente `PipelineHealthChip` en `DashboardLayout` (no reemplaza el banner — coexisten). Muestra un dot de color + porcentaje agregado, con una **barra de porcentaje horizontal** para coverage del universo. Click abre `PipelineHealthDrawer` con detalle por ciclo, barras de progreso por heartbeat, ventana de warmup activa y errores recientes.
- **Indicador de warmup**: cuando `market_state.is_warmup=true` (09:30-10:30 ET), el chip muestra un badge "WARMUP" en amber y el drawer explica que las métricas dependientes de tick (regime, RS) son menos confiables.

## Non-goals

- **No** modifica el comportamiento del scheduler (no introduce el `MARKET_WARMUP_MIN` guard discutido antes — eso es otro change).
- **No** cambia cómo `MarketRegimeEngine` calcula (no cachea, no devuelve último análisis post-close — eso es otro change).
- **No** persiste históricos largos de heartbeats — sólo el último por `cycle_name` (upsert). El historial vive en logs.
- **No** agrega métricas de latencia de Polygon/yfinance ni alerting externo — sólo visibilidad sobre el pipeline propio.

## Capabilities

### New Capabilities
(ninguna)

### Modified Capabilities
- `data-health-monitoring`: extiende el endpoint, agrega persistencia de heartbeats, y reemplaza el contrato "banner-on-error" por "chip-always-on + banner-on-error".

## Impact

- **Code**:
  - Backend: nuevo modelo `PipelineHeartbeat` + migración Alembic; extensión de [health.py:build_health_snapshot](../../../backend/app/api/v1/endpoints/health.py#L21); nuevo helper `pipeline_heartbeat.py` con `record_cycle()` invocado al final de cada ciclo del scheduler ([scheduler.py:362-399](../../../backend/app/data/scheduler.py#L362-L399)); coverage query contra `StockMetrics` filtrado por QUALITY_FILTERS.
  - Frontend: nuevo `PipelineHealthChip` + `PipelineHealthDrawer` en `components/layout/`; integración en [DashboardLayout.tsx](../../../frontend/components/layout/DashboardLayout.tsx); tipos extendidos en `types/health.ts`.
- **APIs**: `/api/v1/health/data-freshness` gana campos. No breaking.
- **DB**: 1 tabla nueva (`pipeline_heartbeats`), ~5 filas (una por ciclo). Negligible.
- **Dependencias**: ninguna nueva.
