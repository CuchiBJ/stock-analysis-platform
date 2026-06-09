## Context

`DataHealthBanner` actual ([frontend/components/layout/DataHealthBanner.tsx](../../../frontend/components/layout/DataHealthBanner.tsx)) polea `/api/v1/health/data-freshness` cada 60s y solo se renderiza si hay `is_stale` o `recent_errors_24h > 0`. El endpoint ([backend/app/api/v1/endpoints/health.py:21](../../../backend/app/api/v1/endpoints/health.py#L21)) infiere staleness a nivel de fecha (`max(StockMetrics.date) vs max(StockPrice.date)`) y cuenta errores del decorador `@track_task_errors`.

Lo que no ve hoy el operador:
- **Cuándo** se actualizó por última vez cada ciclo (price/FAST/SLOW/realtime). Las marcas viven en memoria en [scheduler.py:329-332](../../../backend/app/data/scheduler.py#L329-L332).
- **Cuántos símbolos del universo quality** tienen métricas frescas para hoy (coverage parcial).
- **Si estamos en la ventana de warmup** (09:30-10:30 ET) donde las métricas dependientes de tick son ruidosas.

El usuario quiere visualización continua con barra(s) de porcentaje, no solo un banner-on-error.

## Goals / Non-Goals

**Goals:**
- Persistir el estado del último ciclo de cada loop del scheduler en DB para que sobreviva reinicios y sea consultable por endpoint.
- Exponer coverage del universo quality como porcentaje accionable (no solo "stale sí/no").
- Hacer visible la ventana de warmup como flag explícito que el frontend pueda renderizar.
- Frontend always-on: chip compacto en el header con dot + % coverage, barra de progreso, y drawer de detalle clickeable.
- Mantener compatibilidad con el banner actual y con el CLI `health_check.py`.

**Non-Goals:**
- No cambiar el comportamiento del scheduler ni de `MarketRegimeEngine`.
- No historizar heartbeats — upsert único por `cycle_name`.
- No alerting externo (Slack/PagerDuty); el chip es la única salida nueva.
- No reescribir `DataHealthBanner`; sigue para errores serios.

## Decisions

### D1. Tabla `pipeline_heartbeats` con upsert por `cycle_name`

Una fila por ciclo: `cycle_name` (PK), `last_run_at`, `last_success_at`, `last_duration_seconds`, `symbols_processed`, `symbols_expected`, `status` (`ok`|`partial`|`failed`), `last_error_message` (nullable), `updated_at`.

**Por qué upsert vs append:** el operador siempre quiere "estado actual", no historial. El historial vive en logs estructurados y en `scheduler_errors`. Append agregaría volumen sin valor operativo (5 ciclos × N días).

**Alternativa rechazada:** Redis/in-memory. Pierde estado en reinicios; el scheduler reinicia con frecuencia durante desarrollo y un chip en rojo post-reinicio (sin heartbeats) sería falso positivo.

### D2. `record_cycle()` helper al final de cada loop del scheduler

Helper sincrónico en `backend/app/data/pipeline_heartbeat.py`:

```python
async def record_cycle(
    db, cycle_name: str, *,
    duration_seconds: float,
    symbols_processed: int | None = None,
    symbols_expected: int | None = None,
    status: Literal["ok", "partial", "failed"] = "ok",
    error_message: str | None = None,
) -> None
```

Invocado en los 5 puntos de [scheduler.py:362-419](../../../backend/app/data/scheduler.py#L362-L419) (price, fast_metrics, slow_metrics, realtime_discovery, post_close_cycle). Falla silenciosa (log warning) para no romper el scheduler si la DB está caída.

**Por qué helper vs decorador:** las funciones a instrumentar ya están envueltas en `@track_task_errors`, y necesitan capturar `symbols_processed` que es retornado/calculado dentro del cuerpo. Un decorador no tendría acceso fácil. Helper explícito mantiene el código del scheduler legible.

### D3. Coverage = `count(StockMetrics.date == today) / count(quality_universe)` con QUALITY_FILTERS

Calculado on-demand en `build_health_snapshot()`, no persistido. Una query agregada barata (~ms).

**`expected`** = count de símbolos con `StockPrice.date == today` aplicando QUALITY_FILTERS (price ≥ 5, vol ≥ 500k, adr ≥ 2). 
**`actual`** = mismo conjunto pero con `StockMetrics.date == today AND updated_at >= today_open_et`.

**Por qué no usar `symbols_processed` del heartbeat:** el heartbeat refleja el último ciclo SLOW; si el SLOW corre cada 30 min, la coverage real en la DB puede ser mayor que el último run individual. Query directa da número real.

### D4. `market_state` calculado server-side con `pytz` US/Eastern

`is_open`: weekday Mon-Fri AND `09:30 <= now <= 16:00 ET`.
`is_warmup`: `is_open AND 09:30 <= now <= 10:30 ET` (constante `MARKET_WARMUP_END = time(10, 30)`).
`minutes_since_open`: int (negativo si pre-market).
`session_phase`: `"pre_market"` | `"warmup"` | `"regular"` | `"after_hours"` | `"closed"`.

**Por qué server-side:** evita que cada cliente recalcule con timezone potencialmente mal seteada del browser. El backend ya usa `pytz` para el scheduler.

### D5. Frontend: chip + drawer separados, ambos always-on

`PipelineHealthChip` (~60px de ancho) en el header de `DashboardLayout`, a la derecha del logo. Estructura visual:

```
[●] 98% [warmup]   ← dot color + coverage % + warmup badge (condicional)
```

Click abre `PipelineHealthDrawer` (sheet desde la derecha, ancho ~400px). Contenido:
- Header: `Pipeline health · last poll Xs ago`
- Bloque "Coverage": barra de progreso (TailwindCSS) `expected / actual` con %.
- Bloque "Cycles": una fila por ciclo del heartbeat con `last_run_at` relativo ("2m ago"), duration, status dot, barra fina de progreso si tiene `symbols_processed/expected`.
- Bloque "Market state": `session_phase`, `minutes_since_open`, banner amber si `is_warmup`.
- Bloque "Recent errors": reutiliza los `recent_errors` ya devueltos por el endpoint.

**Color del dot del chip** (peor caso):
- 🔴 rojo si algún ciclo `status=failed` O `recent_errors_24h > 0`.
- 🟡 amber si algún ciclo `status=partial` O `is_stale=true` O coverage < 95% O `is_warmup=true`.
- 🟢 verde en otro caso.

**Por qué TanStack Query:** ya se usa en el resto del frontend; el chip puede hacer `useQuery` con `refetchInterval: 30_000` y compartir cache con el banner (que poléa cada 60s — se unifica en 30s).

### D6. Poll cadence: 30 segundos

El banner actual poléa cada 60s; el chip baja a 30s. Razón: la coverage se mueve rápido durante FAST cycles (cada 5 min), y el `minutes_since_open` debe verse incrementar para que el usuario perciba "vivo". 30s = ~10 polls por FAST cycle, suficiente granularidad sin presión sobre el endpoint (query es de pocos ms).

## Risks / Trade-offs

- **[Heartbeat puede mentir si scheduler crashea entre cycles]** → `last_run_at` quedaría viejo. Mitigation: el frontend calcula `age_seconds` y muestra ciclo como `stale` si `age > expected_interval × 2` (ej. SLOW expected 1800s, stale si > 3600s).
- **[Coverage query puede ser lenta si el universo crece]** → Mitigation: índice existente en `(symbol, date)` cubre el filtro; si crece >50k símbolos, agregar índice parcial `WHERE date = current_date`.
- **[Chip + banner compitiendo por atención]** → Mitigation: chip es discreto (texto pequeño, sin background), banner es full-width rojo/amber. Jerarquía visual diferenciada. Banner sólo se renderiza en condiciones que el chip también marca, pero el banner exige scroll-to-top awareness.
- **[Reinicio del scheduler deja heartbeats viejos en DB]** → Mitigation: el frontend muestra `last_run_at` relativo + status `stale` automáticamente. Y `record_cycle` se llama en cada iteración del loop, así que el primer ciclo post-reinicio refresca.
- **[`is_warmup=true` puede asustar al operador que no entendió por qué]** → Mitigation: el drawer incluye una línea explicativa: "Durante warmup, métricas dependientes de tick (regime, RS) son ruidosas. Mejor confiar en setups con state ≥ 1 día."

## Migration Plan

1. Migración Alembic crea `pipeline_heartbeats` (tabla vacía, sin backfill — los ciclos llenan en el primer run).
2. Deploy backend con `record_cycle` invocaciones y endpoint extendido. Banner actual sigue funcionando (campos viejos intactos).
3. Deploy frontend con chip + drawer. Banner queda como está.
4. Rollback: revert frontend (chip desaparece, banner sigue). Si hay que revertir backend, los campos nuevos del JSON desaparecen y el banner ignora lo que no conoce. La tabla puede quedar (no rompe nada).

## Open Questions

- ¿Mostrar el chip también en páginas auth/login? → No por default; vive en `DashboardLayout` que cubre las páginas operacionales.
- ¿Quitar `MARKET_WARMUP_END = 10:30` a config? → Por ahora constante en código; si el usuario quiere ajustar el rango, se mueve a `app/core/config.py` después.
